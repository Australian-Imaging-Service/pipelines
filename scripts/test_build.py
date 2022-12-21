from click.testing import CliRunner
from arcana.core.cli.deploy import make_app
from arcana.core.utils.testing import show_cli_trace


runner = CliRunner()

results = runner.invoke(
    make_app,
    [
        "./australianimagingservice",
        "--registry",
        "ghcr.io",
        "--license-src",
        "./licenses",
        "--push",
        "--check-registry",
        "--loglevel",
        "info",
    ],
    catch_exceptions=False,
)

print(show_cli_trace(results))
