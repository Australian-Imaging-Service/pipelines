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

# nohup pytest tests/test_t1_preprocess.py > tests/test_t1_preprocess_OUTPUT.txt &
nohup pytest tests/test_dwi_preprocess.py > tests/test_dwi_preprocess_OUTPUT.txt &
