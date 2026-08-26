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

# --use-local-packages bakes each package's *locally installed* version into the built
# image, so this host's installed versions must exactly match the pins in preprocess.yaml.
# Re-pin last, since the installs above (esp. `pip install -I`) can silently drag these
# back to latest — which has broken things twice now:
#   - setuptools>=82 removed pkg_resources, which pydra2app still imports.
#   - frametree only got picked up here because it happens to be declared in
#     preprocess.yaml's packages: list. pydra2app itself hardcodes its OWN companion
#     versions for the internal xnat-cs-entrypoint tooling env — frametree-xnat==0.6.15
#     and pydra2app-xnat==0.8.5 (not declared anywhere in this repo, not affected by
#     anything pinned on this host) — and 0.8.5 still hardcodes MedImage.constant, an
#     enum member frametree renamed to MedImage.dataset in 0.17. So frametree here MUST
#     stay <=0.16.x to match pydra2app's own hardcoded pydra2app-xnat==0.8.5, regardless
#     of what any locally-installed pydra2app-xnat reports.
#
# On this host, re-installing over a newer version has left stale duplicate .dist-info
# dirs sitting alongside the pinned one (e.g. setuptools-84.0.0.dist-info next to
# setuptools-81.0.0.dist-info), which importlib.metadata — what pydra2app's
# --use-local-packages check actually queries, NOT `pip show` — picks up instead of the
# pin. Strip any non-matching dist-info before each pin so this can't recur silently, and
# fail fast (seconds, not a multi-hour build) if importlib.metadata still disagrees.
declare -A PINNED_VERSIONS=(
    [setuptools]="81.0.0"
    [frametree]="0.16.3"
    [pydra2app]="0.20.7"
)
SITE_PACKAGES="$("$PYENV_PYTHON" -c "import sysconfig; print(sysconfig.get_path('purelib'))")"
for pkg in "${!PINNED_VERSIONS[@]}"; do
    version="${PINNED_VERSIONS[$pkg]}"
    find "$SITE_PACKAGES" -maxdepth 1 -iname "${pkg}-*.dist-info" ! -iname "${pkg}-${version}.dist-info" -exec rm -rf {} +
    pip install "${pkg}==${version}"
    actual="$("$PYENV_PYTHON" -c "import importlib.metadata; print(importlib.metadata.version('${pkg}'))")"
    if [ "$actual" != "$version" ]; then
        echo "ERROR: importlib.metadata reports ${pkg} ${actual}, expected ${version} (pip show may disagree — see $SITE_PACKAGES)" >&2
        exit 1
    fi
done

# Smoke-test the exact import that crashed inside the container (frametree/pydra2app-xnat
# API incompatibility) — catches it here in under a second, instead of after the
# multi-hour docker build below.
"$PYENV_PYTHON" -c "import pydra2app.xnat"

# Use pyenv's own resolution rather than bare `pytest`/`python` on PATH — on this host
# something (e.g. an FSL environment script) puts a non-pyenv python ahead of
# ~/.pyenv/shims for the bare `python` name, which previously caused pydra2app's
# in-process package-version checks to see that other Python's setuptools instead of
# the one pinned in this venv.
nohup "$PYENV_PYTHON" -m pytest tests/test_t1_preprocess.py > tests/test_t1_preprocess_OUTPUT.txt &
