import logging
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

app = typer.Typer(no_args_is_help=True)
pricing_app = typer.Typer(no_args_is_help=True, help="Manage model pricing table")
app.add_typer(pricing_app, name="pricing")
console = Console()


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
    table.add_column("Trial", style="cyan", max_width=60)
    table.add_column("Methodology")
    table.add_column("Context")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Gate", justify="center")
    table.add_column("USD", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Wall(s)", justify="right")

    for t in trials:
        s = results.get(t.id)
        if s is None:
            table.add_row(t.id, t.methodology_id, t.repo_context_id, t.model, "[dim]pending[/]", "", "", "", "")
        elif s.get("skipped"):
            table.add_row(t.id, t.methodology_id, t.repo_context_id, t.model, "[yellow]skipped[/]", "", "", "", "")
        elif s.get("error"):
            table.add_row(t.id, t.methodology_id, t.repo_context_id, t.model, "[red]ERROR[/]", "", "", "", "")
        else:
            gate = "[green]PASS[/]" if s["passed"] else "[red]FAIL[/]"
            usd = f"${s['usd']:.3f}" if s["usd"] else ""
            tokens = f"{s['tokens']:,}" if s["tokens"] else ""
            wall = f"{s['wall_seconds']:.1f}"
            table.add_row(t.id, t.methodology_id, t.repo_context_id, t.model, "[green]done[/]", gate, usd, tokens, wall)

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
    db: Path = typer.Option(Path("results.db"), help="Database path"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug logging"),
):
    """Expand the trial matrix and execute all trials."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    tasks = list_tasks() if task == "all" else [task]
    methodologies = list_methodologies() if methodology == "all" else [methodology]
    repo_contexts = list_repo_contexts() if repo_context == "all" else [repo_context]
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

        execute_all(trials, conn, delay=delay, on_progress=on_progress)

    done = [r for r in results.values() if not r.get("skipped") and not r.get("error")]
    passed = sum(1 for r in done if r.get("passed"))
    failed = sum(1 for r in done if r.get("passed") is False)
    errors = sum(1 for r in results.values() if r.get("error"))
    total_usd = sum(r.get("usd", 0) for r in done)

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
def report():
    typer.echo("Not implemented yet (P3)", err=True)
    raise typer.Exit(code=1)


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
