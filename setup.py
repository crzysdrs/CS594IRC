#!/usr/bin/env python
"""
Setup.py
Installs dependencies and all entry points for the IRC project.
"""
from setuptools import setup

setup(
    name='IRC594',
    version='1.0',
    description='IRC Client For CS594',
    author='Mitch Souders',
    author_email='msouders@pdx.edu',
    scripts=[
        'src/irc_server', 'src/irc_bot', 'src/math_bot'
    ],
    package_dir={'': 'src'},
    py_modules=[
        'IRC'
    ],
    entry_points={
        'console_scripts': [
            'irc_client = IRC.Client:main'
        ],
    },
    #url='',
    #packages=['distutils', 'distutils.command'],
    install_requires=[
        'petname',
        'jsonschema',
        'more_itertools',
        'mathjspy',
    ]
)
