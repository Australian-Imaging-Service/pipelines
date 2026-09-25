#!/usr/bin/env python
"""Lint YAML files, tolerating the handful of custom tags this repo actually uses
(currently just Pydra2App's '!join').

A drop-in replacement for pre-commit-hooks' 'check-yaml', which fails outright on
any tag it doesn't recognise. Rather than reimplementing the tag constructors here
(and risking them drifting from the real ones), this loads each file through
P2AImage._load_yaml - pydra2app's own loader, which registers its actual '!join'
constructor on yaml.SafeLoader before parsing - so the check accepts exactly what
pydra2app itself would accept when it loads these spec files.
"""

from __future__ import annotations

import argparse
import sys
import typing as ty

import yaml
from pydra2app.core.image.base import P2AImage


def main(argv: ty.Optional[ty.Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("filenames", nargs="*")
    args = parser.parse_args(argv)

    retval = 0
    for filename in args.filenames:
        try:
            P2AImage._load_yaml(filename)
        except yaml.YAMLError as exc:
            print(f"{filename}: {exc}")
            retval = 1
    return retval


if __name__ == "__main__":
    sys.exit(main())
