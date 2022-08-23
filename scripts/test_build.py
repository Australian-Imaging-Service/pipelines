from click.testing import CliRunner
from arcana.cli.deploy import build
from arcana.test.utils import show_cli_trace


runner = CliRunner()

results = runner.invoke(
    build,
    [
        "./specs",
        "australian-imaging-service",
        "--registry",
        "ghcr.io",
        "--license-dir",
        "./licenses",
        "--push",
        "--check-registry",
        "--loglevel",
        "info",
    ],
    catch_exceptions=False,
)

print(show_cli_trace(results))
