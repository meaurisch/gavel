import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.table import Table

from core.db import connect
from core.executor import execute_all
from core.matrix import expand
from core.models import Trial
from core.methodology_loader import list_methodologies
from core.repo_context_loader import list_repo_contexts
from core.task_loader import list_tasks


def _force_utf8(streams):
    for s in streams:
        if hasattr(s, "reconfigure") and getattr(s, "encoding", None) != "utf-8":
            s.reconfigure(encoding="utf-8")


_force_utf8([sys.stdout, sys.stderr])

app = typer.Typer(no_args_is_help=True)
pricing_app = typer.Typer(no_args_is_help=True, help="Manage model pricing table")
app.add_typer(pricing_app, name="pricing")
console = Console()


def _summarize(results: dict[str, dict]) -> tuple[int, int, int, float]:
    """Aggregate execution summaries into (passed, failed, errors, total_usd).

    passed/failed only count trials with a meaningful gate verdict (not
    skipped, not errored). total_usd sums every non-skipped trial — an
    errored trial can still carry real billed cost (e.g. "agent produced an
    empty diff") and must not be dropped from the printed total.
    """
    ran = [r for r in results.values() if not r.get("skipped")]
    done = [r for r in ran if not r.get("error")]
    passed = sum(1 for r in done if r.get("passed"))
    failed = sum(1 for r in done if r.get("passed") is False)
    errors = sum(1 for r in ran if r.get("error"))
    total_usd = sum(r.get("usd") or 0 for r in ran)
    return passed, failed, errors, total_usd


def _grid_table(trials: list[Trial]) -> Table:
    table = Table(title="Trial Grid")
    table.add_column("Trial ID", style="cyan")
    table.add_column("Task")
    table.add_column("Methodology")
    table.add_column("Context")
    table.add_column("Model")
    table.add_column("Runner")
    table.add_column("Rep", justify="right")
    for t in trials:
        table.add_row(t.id, t.task_id, t.methodology_id, t.repo_context_id, t.model, t.runner, str(t.rep))
    return table


def _progress_table(trials: list[Trial], results: dict[str, dict]) -> Table:
    table = Table(title="Execution Progress")
    table.add_column("Trial", style="cyan")
    table.add_column("Methodology")
    table.add_column("Context")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Gate", justify="center")
    table.add_column("USD", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Wall(s)", justify="right")

    for t in trials:
        label = f"{t.task_id} #{t.rep}"
        s = results.get(t.id)
        if s is None:
            table.add_row(label, t.methodology_id, t.repo_context_id, t.model, "[dim]pending[/]", "", "", "", "")
        elif s.get("skipped"):
            table.add_row(label, t.methodology_id, t.repo_context_id, t.model, "[yellow]skipped[/]", "", "", "", "")
        elif s.get("error"):
            table.add_row(label, t.methodology_id, t.repo_context_id, t.model, "[red]ERROR[/]", "", "", "", "")
        else:
            gate = "[green]PASS[/]" if s["passed"] else "[red]FAIL[/]"
            usd = f"${s['usd']:.3f}" if s["usd"] else ""
            tokens = f"{s['tokens']:,}" if s["tokens"] else ""
            wall = f"{s['wall_seconds']:.1f}"
            table.add_row(label, t.methodology_id, t.repo_context_id, t.model, "[green]done[/]", gate, usd, tokens, wall)

    return table


@app.command()
def run(
    task: str = typer.Option("all", help="Task ID or 'all'"),
    methodology: str = typer.Option("all", help="Methodology ID or 'all'"),
    repo_context: str = typer.Option("all", help="Repo context ID or 'all'"),
    model: str = typer.Option("", help="Comma-separated model IDs"),
    runner: str = typer.Option("claude-code", help="Runner name"),
    reps: int = typer.Option(3, help="Repetitions per cell"),
    full_matrix: bool = typer.Option(False, "--full-matrix", help="Ignore task affinity"),
    delay: float = typer.Option(0.0, help="Seconds between trials (rate limiting)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print trial grid and exit"),
    keep_worktree: bool = typer.Option(False, "--keep-worktree", help="Don't tear down worktrees (debug: inspect laid-down files)"),
    db: Path = typer.Option(Path("results.db"), help="Database path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
):
    """Expand the trial matrix and execute all trials."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    def _ids(value: str, list_all) -> list[str]:
        if value == "all":
            return list_all()
        return [v.strip() for v in value.split(",") if v.strip()]

    tasks = _ids(task, list_tasks)
    methodologies = _ids(methodology, list_methodologies)
    repo_contexts = _ids(repo_context, list_repo_contexts)
    models = [m.strip() for m in model.split(",") if m.strip()]

    if not models:
        console.print("[red]Error: --model is required (comma-separated model IDs)[/]")
        raise typer.Exit(code=2)

    if not tasks:
        console.print("[red]Error: no tasks found[/]")
        raise typer.Exit(code=2)

    if "baseline" not in methodologies:
        console.print("[yellow]Warning: 'baseline' methodology not included — without it you can't prove a methodology adds value[/]")

    trials = expand(tasks, methodologies, repo_contexts, models, runner, reps, full_matrix)

    if not trials:
        console.print("[yellow]No trials to run (methodology/harness filtering removed all combinations)[/]")
        raise typer.Exit(code=0)

    console.print(
        f"\n[bold]{len(trials)} trials[/] = {len(tasks)} tasks x "
        f"{len(set(t.methodology_id for t in trials))} methodologies x "
        f"{len(set(t.repo_context_id for t in trials))} contexts x "
        f"{len(models)} models x {reps} reps\n"
    )

    if dry_run:
        console.print(_grid_table(trials))
        raise typer.Exit(code=0)

    conn = connect(db)
    results: dict[str, dict] = {}

    with Live(_progress_table(trials, results), console=console, refresh_per_second=1) as live:
        def on_progress(i: int, trial: Trial, summary: dict):
            results[trial.id] = summary
            live.update(_progress_table(trials, results))

        execute_all(trials, conn, delay=delay, on_progress=on_progress, keep_worktree=keep_worktree)

    passed, failed, errors, total_usd = _summarize(results)

    console.print(f"\n[bold]Done.[/] {passed} passed, {failed} failed, {errors} errors. Total cost: ${total_usd:.2f}")


@app.command()
def grade(
    db: Path = typer.Option(Path("results.db"), help="Database path"),
    port: int = typer.Option(8247, help="Server port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
):
    """Launch the pairwise grading UI."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    import uvicorn
    from ui.server import app as fastapi_app, set_db_path

    set_db_path(db)
    console.print(f"[bold]Grading UI[/] → http://localhost:{port}")
    uvicorn.run(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level="debug" if verbose else "warning",
    )


@app.command()
def report(
    axis: str = typer.Option("methodology", help="Comparison axis: methodology, model, repo_context, runner"),
    task: str = typer.Option("", help="Pin to one task"),
    methodology: str = typer.Option("", help="Pin to one methodology"),
    repo_context: str = typer.Option("", help="Pin to one repo context"),
    model: str = typer.Option("", help="Pin to one model"),
    runner: str = typer.Option("", help="Pin to one runner"),
    db: Path = typer.Option(Path("results.db"), help="Database path"),
    out_dir: Path = typer.Option(Path("reports"), help="Directory for the HTML artifact"),
    no_html: bool = typer.Option(False, "--no-html", help="Terminal summary only"),
):
    """Rank the chosen axis: Bradley-Terry scores with CIs, gate pass rates,
    cost rollup, analyzer flags, the quality/cost Pareto frontier, and the
    stakes-based picks — in the terminal and as a self-contained HTML file."""
    from datetime import datetime, timezone

    from grading.aggregate import build_report
    from grading.pairwise import AXIS_FIELDS
    from grading.report_html import render_report_html

    if axis not in AXIS_FIELDS:
        console.print(f"[red]Unknown axis {axis!r}; valid: {', '.join(sorted(AXIS_FIELDS))}[/]")
        raise typer.Exit(code=2)
    if not db.exists():
        console.print(f"[red]No database at {db} — run some trials first.[/]")
        raise typer.Exit(code=2)

    cell = {
        "task_id": task,
        "methodology_id": methodology,
        "repo_context_id": repo_context,
        "model": model,
        "runner": runner,
    }
    # Pinning the comparison axis itself would make every pair same-value.
    cell.pop(AXIS_FIELDS[axis], None)

    conn = connect(db)
    data = build_report(conn, axis, cell)

    scope = ", ".join(f"{k}={v}" for k, v in data.cell.items()) or "all cells"
    console.print(f"\n[bold]Comparison axis:[/] {axis}   [bold]Scope:[/] {scope}")
    console.print(
        f"[dim]{data.n_judgments} blind judgment(s) across {data.n_sessions} grading session(s)[/]\n"
    )

    table = Table(title=f"{axis} ranking (Bradley-Terry)")
    table.add_column(axis, style="cyan")
    table.add_column("Elo", justify="right")
    table.add_column("95% CI (Elo)", justify="right")
    table.add_column("Comps", justify="right")
    table.add_column("Hidden gate", justify="right")
    table.add_column("Trials", justify="right")
    table.add_column("Mean $", justify="right")
    table.add_column("Total $", justify="right")
    table.add_column("Frontier", justify="center")

    def _elo(x: float) -> str:
        import math
        return f"{1000 + 400 * x / math.log(10):.0f}"

    ranked = sorted(
        data.summaries,
        key=lambda s: -(s.bt_strength if s.bt_strength is not None else float("-inf")),
    )
    for s in ranked:
        ci = f"{_elo(s.bt_ci[0])}–{_elo(s.bt_ci[1])}" if s.bt_ci else "—"
        marks = []
        if s.value == data.picks.get("high_stakes"):
            marks.append("[bold blue]quality pick[/]")
        if s.value == data.picks.get("routine"):
            marks.append("[bold green]budget pick[/]")
        hidden = s.tier_pass_rates.get("hidden")
        table.add_row(
            s.value + (" " + " ".join(marks) if marks else ""),
            f"{s.elo:.0f}" if s.elo is not None else "—",
            ci,
            str(s.n_comparisons),
            f"{hidden * 100:.0f}%" if hidden is not None else "—",
            str(s.n_trials),
            f"${s.mean_usd:.3f}" if s.mean_usd is not None else "—",
            f"${s.total_usd:.2f}",
            "[green]yes[/]" if s.on_frontier else ("—" if s.bt_strength is None else "no"),
        )
    console.print(table)

    flag_items = (
        [f"non-discriminating task: {t}" for t in data.flags.non_discriminating_tasks]
        + [f"flaky task: {t}" for t in data.flags.flaky_tasks]
        + list(data.flags.cost_quality_notes)
    )
    if flag_items:
        console.print("\n[bold]Analyzer flags[/]")
        for f in flag_items:
            console.print(f"  [yellow]•[/] {f}")

    if data.picks.get("high_stakes"):
        console.print(
            f"\n[bold]High-stakes pick:[/] {data.picks['high_stakes']}   "
            f"[bold]Routine pick:[/] {data.picks['routine']}"
        )
    elif data.n_judgments == 0:
        console.print(
            "\n[yellow]No blind judgments for this axis yet — the ranking columns stay "
            "empty until you grade ([bold]python cli.py grade[/]).[/]"
        )

    if not no_html:
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_path = out_dir / f"report-{axis}-{stamp}.html"
        out_path.write_text(
            render_report_html(data, generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
            encoding="utf-8",
        )
        console.print(f"\n[bold]HTML artifact:[/] {out_path}")


@app.command()
def setup(
    check: bool = typer.Option(False, "--check", help="Report state without changing anything"),
    skip_vendor: bool = typer.Option(False, "--skip-vendor", help="Skip vendoring methodology packs"),
):
    """One-shot bootstrap: clone task repos, rebuild the deterministic
    task-base commits, and vendor the methodology packs."""
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from bootstrap_repos import bootstrap

    failed = False

    results = bootstrap(check_only=check)
    table = Table(title="Task repos / base commits")
    table.add_column("Base")
    table.add_column("Status")
    table.add_column("Detail")
    for base_id, status, detail in results:
        style = {"ok": "green", "missing": "yellow", "error": "red"}[status]
        table.add_row(base_id, f"[{style}]{status}[/]", detail)
        failed = failed or status != "ok"
    console.print(table)

    if not check and not skip_vendor:
        import yaml as _yaml
        from vendor_setup import vendor_methodology

        for manifest in sorted(Path("methodologies").glob("*/manifest.yaml")):
            raw = _yaml.safe_load(manifest.read_text(encoding="utf-8"))
            if not raw.get("source"):
                continue
            mid = manifest.parent.name
            vendor_dir = manifest.parent / "vendor"
            if vendor_dir.exists() and any(vendor_dir.iterdir()):
                console.print(f"[dim]vendor pack {mid}: already present[/]")
                continue
            try:
                vendor_methodology(mid)
                console.print(f"[green]vendor pack {mid}: vendored[/]")
            except Exception as e:
                console.print(f"[red]vendor pack {mid}: {e}[/]")
                failed = True

    if failed:
        raise typer.Exit(code=1)
    console.print("[bold green]Setup complete.[/] Run [bold]python cli.py doctor[/] to verify toolchains.")


@app.command()
def demo(
    db: Path = typer.Option(Path("results-demo.db"), help="Demo database path"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing demo DB"),
):
    """Seed a synthetic demo database (zero API spend, no repos needed) so you
    can try the grading UI and the report right away."""
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from seed_demo import seed_demo

    if db.exists():
        if not force:
            console.print(f"[yellow]{db} already exists — pass --force to overwrite.[/]")
            raise typer.Exit(code=1)
        db.unlink()

    seed_demo(db)
    console.print(f"[green]Demo data seeded into {db}[/] (ids are prefixed 'demo-' — this is synthetic showcase data).\n")
    console.print("Try it:")
    console.print(f"  [bold]python cli.py grade  --db {db}[/]   # blind pairwise grading UI")
    console.print(f"  [bold]python cli.py report --db {db}[/]   # ranking + Pareto frontier artifact")


@app.command()
def doctor():
    """Check toolchains, task repos, vendor packs, and pricing readiness."""
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from doctor import run_all_checks

    rows = run_all_checks()
    table = Table(title="setup-bench doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    table.add_column("Hint", style="dim")

    hard_fail = False
    for r in rows:
        if r.ok:
            status = "[green]OK[/]"
        elif r.required:
            status = "[red]FAIL[/]"
            hard_fail = True
        else:
            status = "[yellow]WARN[/]"
        table.add_row(r.name, status, r.detail, "" if r.ok else r.hint)
    console.print(table)

    if hard_fail:
        console.print("[red]Some required checks failed.[/]")
        raise typer.Exit(code=1)
    console.print("[green]Environment ready[/] (warnings only affect the task families noted).")


@pricing_app.command("list")
def pricing_list():
    """Show the current model pricing table."""
    from cost.pricing import load_pricing

    models, aliases = load_pricing()
    table = Table(title="Model Pricing (USD per million tokens)")
    table.add_column("Model", style="cyan")
    table.add_column("Vendor")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Cache Read", justify="right")

    for model_id, p in sorted(models.items()):
        table.add_row(
            model_id, p.vendor,
            f"${p.input_per_mtok:.2f}",
            f"${p.output_per_mtok:.2f}",
            f"${p.cache_read_per_mtok:.3f}",
        )

    if aliases:
        table.add_section()
        for alias, target in sorted(aliases.items()):
            table.add_row(f"{alias} ->", target, "", "", "", style="dim")

    console.print(table)


@pricing_app.command("fetch")
def pricing_fetch(
    vendor: str = typer.Option("anthropic,openai", help="Comma-separated vendor filter"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing"),
):
    """Fetch latest pricing from LiteLLM's open dataset."""
    from cost.fetch_pricing import fetch_litellm_pricing
    from cost.pricing import load_pricing, save_pricing

    vendors = {v.strip() for v in vendor.split(",")}
    fetched = fetch_litellm_pricing(vendors)

    if not fetched:
        console.print("[yellow]No models fetched. Check your network and vendor filter.[/]")
        raise typer.Exit(code=1)

    existing_models, aliases = load_pricing()

    added, updated = [], []
    for model_id, p in fetched.items():
        if model_id not in existing_models:
            added.append(model_id)
        elif existing_models[model_id] != p:
            updated.append(model_id)

    if not added and not updated:
        console.print(f"[green]All {len(fetched)} fetched models already up to date.[/]")
        return

    if added:
        console.print(f"[bold]New models:[/] {', '.join(sorted(added))}")
    if updated:
        console.print(f"[bold]Updated models:[/] {', '.join(sorted(updated))}")

    if dry_run:
        console.print("[dim]Dry run — no changes written.[/]")
        return

    merged = {**existing_models, **fetched}
    save_pricing(merged, aliases)
    console.print(f"[green]Wrote {len(merged)} models to pricing.toml[/]")


@pricing_app.command("add")
def pricing_add(
    model_id: str = typer.Argument(help="Model ID (e.g. gpt-4o, claude-sonnet-4-6)"),
    vendor: str = typer.Option(..., "--vendor", "-v", help="Vendor name"),
    input_rate: float = typer.Option(..., "--input", "-i", help="Input cost per MTok"),
    output_rate: float = typer.Option(..., "--output", "-o", help="Output cost per MTok"),
    cache_read: float = typer.Option(None, "--cache-read", "-c", help="Cache read cost per MTok (default: 10%% of input)"),
):
    """Add or update a model in the pricing table."""
    from cost.pricing import ModelPricing, load_pricing, save_pricing

    if cache_read is None:
        cache_read = input_rate * 0.1

    models, aliases = load_pricing()
    action = "Updated" if model_id in models else "Added"
    models[model_id] = ModelPricing(
        vendor=vendor,
        input_per_mtok=input_rate,
        output_per_mtok=output_rate,
        cache_read_per_mtok=cache_read,
    )
    save_pricing(models, aliases)
    console.print(f"[green]{action} {model_id} in pricing.toml[/]")


if __name__ == "__main__":
    app()
