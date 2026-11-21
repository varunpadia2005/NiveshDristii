"""P13-A #7: `python -m niveshdristi` runs the CLI exactly like the `nd`
console-script entry point (same Typer app, exit code propagated)."""

from niveshdristi.cli.main import app

if __name__ == "__main__":
    app()
