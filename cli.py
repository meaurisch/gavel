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
from core.setup_loader import list_setups
from core.task_loader import list_tasks

app = typer.Typer(no_args_is_help=True)
console = Console()


def _grid_table(trials: list[Trial]) -> Table:
    table = Table(title="Trial Grid")
    table.add_column("Trial ID", style="cyan")
    table.add_column("Task")
    table.add_column("Setup")
    table.add_column("Model")
    table.add_column("Runner")
    table.add_column("Rep", justify="right")
    for t in trials:
        table.add_row(t.id, t.task_id, t.setup_id, t.model, t.runner, str(t.rep))
    return table


def _progress_table(trials: list[Trial], results: dict[str, dict]) -> Table:
    table = Table(title="Execution Progress")
    table.add_column("Trial", style="cyan", max_width=60)
    table.add_column("Setup")
    table.add_column("Model")
    table.add_column("Status")
    table.add_column("Gate", justify="center")
    table.add_column("USD", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Wall(s)", justify="right")

    for t in trials:
        s = results.get(t.id)
        if s is None:
            table.add_row(t.id, t.setup_id, t.model, "[dim]pending[/]", "", "", "", "")
        elif s.get("skipped"):
            table.add_row(t.id, t.setup_id, t.model, "[yellow]skipped[/]", "", "", "", "")
        elif s.get("error"):
            table.add_row(t.id, t.setup_id, t.model, "[red]ERROR[/]", "", "", "", "")
        else:
            gate = "[green]PASS[/]" if s["passed"] else "[red]FAIL[/]"
            usd = f"${s['usd']:.3f}" if s["usd"] else ""
            tokens = f"{s['tokens']:,}" if s["tokens"] else ""
            wall = f"{s['wall_seconds']:.1f}"
            table.add_row(t.id, t.setup_id, t.model, "[green]done[/]", gate, usd, tokens, wall)

    return table


@app.command()
def run(
    task: str = typer.Option("all", help="Task ID or 'all'"),
    setup: str = typer.Option("all", help="Setup ID or 'all'"),
    model: str = typer.Option("", help="Comma-separated model IDs"),
    runner: str = typer.Option("claude-code", help="Runner name"),
    reps: int = typer.Option(3, help="Repetitions per cell"),
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
    setups = list_setups() if setup == "all" else [setup]
    models = [m.strip() for m in model.split(",") if m.strip()]

    if not models:
        console.print("[red]Error: --model is required (comma-separated model IDs)[/]")
        raise typer.Exit(code=2)

    if not tasks:
        console.print("[red]Error: no tasks found[/]")
        raise typer.Exit(code=2)

    trials = expand(tasks, setups, models, runner, reps)

    if not trials:
        console.print("[yellow]No trials to run (setup/harness filtering removed all combinations)[/]")
        raise typer.Exit(code=0)

    console.print(f"\n[bold]{len(trials)} trials[/] = {len(tasks)} tasks x {len(set(t.setup_id for t in trials))} setups x {len(models)} models x {reps} reps\n")

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
def grade():
    typer.echo("Not implemented yet (P1.7)", err=True)
    raise typer.Exit(code=1)


@app.command()
def report():
    typer.echo("Not implemented yet (P3)", err=True)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
