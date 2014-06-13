#!/usr/bin/env python

from os.path import exists
from setuptools import setup
import benchtoolz

setup(
    name='benchtoolz',
    version=benchtoolz.__version__,
    description=('Benchmark Python and Cython code'),
    long_description=(open('README.rst').read() if exists('README.rst')
                      else ''),
    url='https://github.com/eriknw/benchtoolz',
    author='https://raw.github.com/eriknw/benchtoolz/master/AUTHORS.md',
    author_email='erik.n.welch@gmail.com',
    maintainer='Erik Welch',
    maintainer_email='erik.n.welch@gmail.com',
    license = 'BSD',
    packages=['benchtoolz'],
    keywords='benchmark benchmarking timeit cython',
    zip_safe=False,
)
