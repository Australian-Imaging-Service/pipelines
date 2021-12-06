import sys
from pathlib import Path
from setuptools import setup, find_packages

# Get version from module inside package
with open(str(Path(__file__).parent / 'requirements.txt')) as f:
    requirements = f.read().splitlines()


setup(
    name='ais',
    version=0.1,
    author='Thomas G. Close',
    author_email='tom.g.close@gmail.com',
    packages=find_packages(exclude=['tests']),
    url='https://github.com/australian-imaging-service/ais',
    license='Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License',
    description=(
        'Scripts to generate containerised analysis pipelines for the '
        'Australian Imaging Service'),
    long_description=open('README.rst').read(),
    install_requires=requirements,
    entry_points={
        'console_scripts': ['deploy_ais = ais.entrypoint:deploy']},
    classifiers=(
        ["Development Status :: 4 - Beta",
         "Intended Audience :: Healthcare Industry",
         "Intended Audience :: Science/Research",
         "License :: OSI Approved :: Apache Software License",
         "Natural Language :: English",
         "Topic :: Scientific/Engineering :: Bio-Informatics",
         "Topic :: Scientific/Engineering :: Medical Science Apps."]
        + ["Programming Language :: Python :: " + str(v)
           for v in ['3.6', '3.7', '3.8', '3.9']]),
    keywords='analysis mri neuroimaging workflows pipelines biomedical')
