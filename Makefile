.PHONY: clean-pyc clean-build docs clean
agent_version = $(shell python -c 'from twindb_agent import __about__; print(__about__.__version__)')
agent_release = 1
build_dir = build
pwd := $(shell pwd)
top_dir = ${pwd}/${build_dir}/rpmbuild
rpmmacros = /usr/lib/rpm/macros:/usr/lib/rpm/redhat/macros:/etc/rpm/macros:support/rpm/rpmmacros

help:
	@echo "clean - remove all build, test, coverage and Python artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "clean-test - remove test and coverage artifacts"
	@echo "lint - check style with flake8"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tests on every Python version with tox"
	@echo "coverage - check code coverage quickly with the default Python"
	@echo "docs - generate Sphinx HTML documentation, including API docs"
	@echo "release - package and upload a release"
	@echo "dist - package"
	@echo "install - install the package to the active Python's site-packages"

clean: clean-build clean-pyc clean-test

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test:
	rm -fr .tox/
	rm -f .coverage
	rm -fr htmlcov/

lint:
	flake8 twindb_agent tests

test:
	@ echo "TwinDB agnet testing"
	# Disable for now, on Ubuntu it doesn't work
	# python setup.py test

test-all:
	tox

coverage:
	coverage run --source twindb-agent setup.py test
	coverage report -m
	coverage html
	open htmlcov/index.html

docs:
	rm -f docs/twindb-agent.rst
	rm -f docs/modules.rst
	sphinx-apidoc -o docs/ twindb-agent
	$(MAKE) -C docs clean
	$(MAKE) -C docs html
	open docs/_build/html/index.html

release: clean
	python setup.py sdist upload
	python setup.py bdist_wheel upload

dist: clean
	python setup.py sdist
	# python setup.py bdist_wheel
	ls -l dist

PYTHON_VERSION = $$(python --version 2>&1 | awk '{ print $$2 }' | awk -F. '{ print $$1"."$$2 }' )
PYTHON_SITE_PACKAGES_DIR = $$(python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")

build: clean
	python setup.py build

install: clean
	@ if test -z "${DESTDIR}" ; \
	then python setup.py install --prefix /usr; \
	else python setup.py install --prefix /usr --root "${DESTDIR}" ; \
		mkdir -p "${DESTDIR}/etc/logrotate.d/" ; \
		install -m 644 support/twindb-agent.logrotate "${DESTDIR}/etc/logrotate.d/twindb-agent" ; \
	fi

# Packaging
package:
	@if ! test -z "`which yum 2>/dev/null`"; then make build-rpm; fi
	@if ! test -z "`which apt-get 2>/dev/null`"; then make deb-dependencies build-deb; fi

# RPM stuff
build-rpm: spec dist
	mkdir -p "${top_dir}/SOURCES"
	mkdir -p "${top_dir}/BUILD"
	mkdir -p "${top_dir}/SRPMS"
	mkdir -p "${top_dir}/RPMS/noarch"
	cp dist/twindb-agent-${agent_version}.tar.gz ${top_dir}/SOURCES/
	rpmbuild --macros=${rpmmacros} --define '_topdir ${top_dir}' -ba support/rpm/twindb-agent.spec

sign-rpm: rpmmacros
	rpm --addsign ${top_dir}/RPMS/noarch/twindb-${client_version}-${client_release}.noarch.rpm

upload-rpm:
	ssh -o StrictHostKeyChecking=no repomaster@repo.twindb.com "mkdir -p /var/lib/twindb/repo-staging/rpm/${rh_release}/x86_64/"
	scp -o StrictHostKeyChecking=no ${top_dir}/RPMS/noarch/twindb-${client_version}-${client_release}.noarch.rpm \
        repomaster@repo.twindb.com:/var/lib/twindb/repo-staging/rpm/${rh_release}/x86_64/

rpmmacros:
	if ! test -f ~/.rpmmacros ; then cp support/rpm/rpmmacros ~/.rpmmacros; fi

spec:
	sed -e "s/@@VERSION@@/${agent_version}/" -e "s/@@RELEASE@@/${agent_release}/" \
		support/rpm/twindb-agent.spec.template > support/rpm/twindb-agent.spec

# Debian stuff
deb_packages = build-essential devscripts debhelper

deb-dependencies:
	@echo "Checking dependencies"
	@for p in ${deb_packages}; \
    do echo -n "$$p ... " ; \
        if test -z "`dpkg -l | grep $$p`"; \
        then \
            echo "$$p ... NOT installed"; \
            apt-get -y install $$p; \
        else \
            echo "installed"; \
        fi ; \
    done

deb-changelog:
	@echo "Generating changelog"
	@export DEBEMAIL="TwinDB Packager (TwinDB packager key) <packager@twindb.com>" ; \
	export version=${agent_version}-${agent_release} ; \
	cd support/deb/ ; \
	rm -f debian/changelog ; \
	export distr=`lsb_release -sc` ; \
	dch -v $$version.$$distr --create --package twindb-agent --distribution $$distr "New version $$version" ;


build-deb: deb-dependencies dist deb-changelog
	mkdir -p "${build_dir}"
	cp "dist/twindb-agent-${agent_version}.tar.gz" "${build_dir}/twindb-agent_${agent_version}.orig.tar.gz"
	tar zxf "${build_dir}/twindb-agent_${agent_version}.orig.tar.gz" -C "${build_dir}"
	cp -LR support/deb/debian/ "${build_dir}/twindb-agent-${agent_version}"
	cd "${build_dir}/twindb-agent-${agent_version}" && debuild -us -uc

