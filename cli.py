import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def run(
    task: str = "all",
    setup: str = "all",
    model: str = "",
    runner: str = "claude-code",
    reps: int = 3,
):
    typer.echo("Not implemented yet (P1.6)", err=True)
    raise typer.Exit(code=1)


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
