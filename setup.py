#!/usr/bin/env python

from setuptools import setup

setup(name='IRC594',
      version='1.0',
      description='IRC Client For CS594',
      author='Mitch Souders',
      author_email='msouders@pdx.edu',
      scripts=[
          'src/irc_server',
          'src/irc_client',
      ],
      package_dir={'':'src'},
      py_modules=[
          'IRC'
      ],
      #url='',
      #packages=['distutils', 'distutils.command'],
      install_requires=[
          'petname',
          'jsonschema',
          'more_itertools',
      ]
  )
