from click.testing import CliRunner
from frametree.core.utils import show_cli_trace
from pydra2app.core.cli import pipeline_entrypoint


runner = CliRunner()
result = runner.invoke(
    pipeline_entrypoint,
    [
        "xnat-cs//20251022122628mrihumanneurot1wpreprocess",
        "--input",
        "T1w",
        "t1_mprage_sag_p2_iso_1_ADNI",
        "--output",
        "parc_image",
        "parc_image",
        "--output",
        "vis_image_fsl",
        "vis_image_fsl",
        "--output",
        "ftt_image_fsl",
        "ftt_image_fsl",
        "--output",
        "vis_image_freesurfer",
        "vis_image_freesurfer",
        "--output",
        "ftt_image_freesurfer",
        "ftt_image_freesurfer",
        "--output",
        "vis_image_hsvs",
        "vis_image_hsvs",
        "--output",
        "ftt_image_hsvs",
        "ftt_image_hsvs",
        "--parameter",
        "Parcellation",
        "desikan",
        "--dataset-hierarchy",
        "subject,session",
        "--ids",
        "TESTSUBJ_01",
        "--command",
        "single_parc",
        "--worker",
        "debug",
        "--work",
        "/work",
        "--dataset-name",
        "default",
        "--logger",
        "frametree",
        "debug",
        "--logger",
        "frametree-xnat",
        "debug",
        "--logger",
        "pydra2app",
        "debug",
        "--logger",
        "pydra2app-xnat",
        "debug",
    ],
    catch_exceptions=True,
)

assert result.exit_code == 0, show_cli_trace(result)


# {
#     // Use IntelliSense to learn about possible attributes.
#     // Hover to view descriptions of existing attributes.
#     // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
#     "version": "0.2.0",
#     "configurations": [
#         {
#             "name": "Run-test",
#             "type": "debugpy",
#             "request": "launch",
#             "program": "${file}",
#             "console": "integratedTerminal",
#             "justMyCode": false,
#             "env": {
#                 "XNAT_USER": "admin",
#                 "XNAT_PASS": "admin",
#                 "XNAT_HOST": "http://localhost:8080",
#             }
#         }
#     ]
# }
