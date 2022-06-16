from click.testing import CliRunner
from arcana.cli.deploy import build


runner = CliRunner()

runner.invoke(build,
              ['./specs', 'australian-imaging-service',
               '--registry', 'ghcr.io',
               '--license-dir', './licenses',
            #    '--push',
               '--loglevel', 'info',
               '--scan'],
              catch_exceptions=False)
