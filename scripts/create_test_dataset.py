from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime
import xnat
import pydicom
from arcana2.core.utils import name2path


parser = ArgumentParser()
parser.add_argument('xnat_server',
                    help="The XNAT server to push the test dataset to")
parser.add_argument('dataset_name',
                    help="The name of the dataset to create")
parser.add_argument('alias', help="Username or token alias to access server with")
parser.add_argument('secret', help="Password or token secret to access server with")
parser.add_argument('--project', default='TEST', help="Project name")
parser.add_argument('--scans', nargs='+', help="Scans to upload",
                    default=['anat__l__t1w', 'anat__l__t2w', 'func__l__bold'])
args = parser.parse_args()


project = args.project  # + datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')

TEST_DICOM_DATA = Path(__file__).parent.parent / 'tests' / 'data' / 'ses-01-dicom'

with xnat.connect(server=args.xnat_server, user=args.alias, password=args.secret) as login:
    login.put(f'/data/archive/projects/{project}')

with xnat.connect(server=args.xnat_server, user=args.alias, password=args.secret) as login:
    xproject = login.projects[project]
    xclasses = login.classes

    # Create subject
    subject_label = f'{project}_SUBJECT'
    xsubject = xclasses.SubjectData(label=subject_label,
                                    parent=xproject)
    # Create session
    session_label = f'{subject_label}_TIMEPOINT'
    xsession = xclasses.MrSessionData(label=session_label,
                                      parent=xsubject)

    for i, sname in enumerate(args.scans, start=1):
        # Create scan
        xscan = xclasses.MrScanData(id=i, type=name2path(sname),
                                    parent=xsession)
        # Create the resource
        xresource = xscan.create_resource('DICOM')
        # Create the dummy files
        sdir = TEST_DICOM_DATA / sname
        for fname in sdir.iterdir():
            if not str(fname).startswith('.'):
                xresource.upload(str(sdir / fname), str(fname))

    # Trigger DICOM header parsing
    login.put(f'/data/experiments/{xsession.id}?pullDataFromHeaders=true')
