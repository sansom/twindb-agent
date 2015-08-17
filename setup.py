#!/usr/bin/env python

# To workaround hard link error
# http://stackoverflow.com/questions/7719380/python-setup-py-sdist-error-operation-not-permitted
# http://bugs.python.org/issue8876#msg208792
import os
del os.link

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read().replace(".. :changelog:", "")

requirements = [
    # TODO: put package requirements here
    "mysql-connector-python"
]

test_requirements = [
    # TODO: put package test requirements here
]


class _AttrDict(dict):

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            # to conform with __getattr__ spec
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

try:
    from twindb_agent import __about__
except ImportError:
    __about__ = _AttrDict()
    with open("twindb_agent/__about__.py") as fp:
        exec(fp.read(), __about__)

setup(
    name="twindb-agent",
    version=__about__.__version__,
    description="TwinDB Agent",
    long_description=readme + '\n\n' + history,
    author="TwinDB Development Team",
    author_email="dev@twindb.com",
    url="https://github.com/twindb/twindb-agent",
    packages=[
        "twindb_agent",
        "twindb_agent.job_type"
    ],
    package_dir={'twindb_agent':
                 'twindb_agent'},
    scripts=["scripts/twindb-agent"],
    include_package_data=True,
    install_requires=requirements,
    license="Apache License Version 2.0",
    zip_safe=False,
    keywords="twindb-agent",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
    ],
    test_suite="tests",
    tests_require=test_requirements
)
