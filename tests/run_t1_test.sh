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

PYENV_PYTHON="$(pyenv which python)"

# setuptools>=82 removed pkg_resources, which pydra2app still imports; --use-local-packages
# requires this host's installed version to exactly match the pin in preprocess.yaml, so keep
# both in sync. Re-pin last, since the installs above (esp. `pip install -I`) can silently
# drag setuptools back to latest.
#
# On this host, re-installing over a newer setuptools has left a stale duplicate
# setuptools-84.0.0.dist-info sitting alongside the pinned one, which importlib.metadata
# (what pydra2app's --use-local-packages check actually queries, NOT `pip show`) picks up
# instead of the pin. Strip any non-matching dist-info first so this can't recur silently.
SITE_PACKAGES="$("$PYENV_PYTHON" -c "import sysconfig; print(sysconfig.get_path('purelib'))")"
find "$SITE_PACKAGES" -maxdepth 1 -name 'setuptools-*.dist-info' ! -name 'setuptools-81.0.0.dist-info' -exec rm -rf {} +
pip install "setuptools==81.0.0"

# Fail fast (seconds, not a multi-hour build) if importlib.metadata still disagrees with pip.
ACTUAL_VERSION="$("$PYENV_PYTHON" -c "import importlib.metadata; print(importlib.metadata.version('setuptools'))")"
if [ "$ACTUAL_VERSION" != "81.0.0" ]; then
    echo "ERROR: importlib.metadata reports setuptools $ACTUAL_VERSION, expected 81.0.0 (pip show may disagree — see $SITE_PACKAGES)" >&2
    exit 1
fi

# Use pyenv's own resolution rather than bare `pytest`/`python` on PATH — on this host
# something (e.g. an FSL environment script) puts a non-pyenv python ahead of
# ~/.pyenv/shims for the bare `python` name, which previously caused pydra2app's
# in-process package-version checks to see that other Python's setuptools instead of
# the one pinned in this venv.
nohup "$PYENV_PYTHON" -m pytest tests/test_t1_preprocess.py > tests/test_t1_preprocess_OUTPUT.txt &
