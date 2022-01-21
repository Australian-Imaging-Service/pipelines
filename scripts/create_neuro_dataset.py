from argparse import ArgumentParser
from pathlib import Path
from datetime import datetime
import xnat
import pydicom
from arcana.core.utils import name2path


parser = ArgumentParser()
parser.add_argument('xnat_server',
                    help="The XNAT server to push the test dataset to")
parser.add_argument('project',
                    help="The name of the project to create")
parser.add_argument('alias', help="Username or token alias to access server with")
parser.add_argument('secret', help="Password or token secret to access server with")
parser.add_argument('--scans', nargs='+', help="Scans to upload",
                    default=['T1w', 'T2w', 'fMRI'])
args = parser.parse_args()


project = args.project  # + datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')

TEST_DATA = Path(__file__).parent.parent / 'tests' / 'data'

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

    for sname in args.scans:
        # Create scan
        dicom_dir = TEST_DATA / 'dicom' / 'ses-01' / sname
        with open(next(dicom_dir.iterdir()), 'rb') as f:
            dcm = pydicom.dcmread(f)
        xscan = xclasses.MrScanData(
            id=dcm.SeriesNumber, type=dcm.SeriesDescription, parent=xsession)
        # Create the DICOM resource
        dicom_xresource = xscan.create_resource('DICOM')
        # Create the dummy files
        
        for fpath in dicom_dir.iterdir():
            if not fpath.name.startswith('.'):
                dicom_xresource.upload(str(fpath), str(fpath.name))

        # Create the NIFTI resource
        niftix_gz_xresource = xscan.create_resource('niftix_gz')
        basename = TEST_DATA / 'nifti' / 'ses-01' / sname
        niftix_gz_xresource.upload(str(basename) + '.nii.gz',
                                   sname + '.nii.gz')
        niftix_gz_xresource.upload(str(basename) + '.json',
                                   sname + '.json')
        

    # Trigger DICOM header parsing
    login.put(f'/data/experiments/{xsession.id}?pullDataFromHeaders=true')
