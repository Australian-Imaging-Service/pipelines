#!/bin/bash
set -e

pyenv activate pipelines

cd /home/ubuntu/git/pydra-tasks-freesurfer
git pull
pip install -e .

cd /home/ubuntu/git/pydra-tasks-fsl
git pull
pip install -e .


cd /home/ubuntu/git/pipelines
# CHECK WHICH BRANCH YOU ARE ON AND PULL THE LATEST CHANGES
git pull
pip install -e .
pip install -I -r requirements.txt
pip install --upgrade pytest

# setuptools>=82 removed pkg_resources, which pydra2app still imports; --use-local-packages
# requires this host's installed version to exactly match the pin in preprocess.yaml, so keep
# both in sync. Re-pin last, since the installs above can silently drag setuptools back to latest.
pip install "setuptools==81.0.0"

nohup pytest tests/test_t1_preprocess.py > tests/test_t1_preprocess_OUTPUT.txt &
