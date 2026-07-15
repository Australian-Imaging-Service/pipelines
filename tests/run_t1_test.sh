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
git pull
pip install -e .
pip install -I -r requirements.txt
pip install --upgrade pytest

nohup pytest tests/test_t1_preprocess.py > tests/test_t1_preprocess_OUTPUT.txt &
