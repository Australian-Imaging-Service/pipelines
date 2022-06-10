from click.testing import CliRunner
from arcana.cli.deploy import build


runner = CliRunner()

runner.invoke(build,
              ['./specs', 'australian-imaging-service',
               '--registry', 'ghcr.io',
               '--license-dir', './licenses',
               '--push',
               '--check-registry'],
              catch_exceptions=False)
