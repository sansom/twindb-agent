#!/usr/bin/env bash

set -e

yum -y install https://dev.mysql.com/get/mysql-community-release-el6-5.noarch.rpm
yum -y install https://repo.twindb.com/twindb-release-latest.noarch.rpm
rpm -Uvh http://download.fedoraproject.org/pub/epel/6/i386/epel-release-6-8.noarch.rpm

packages="
mysql-community-server
mysql-connector-python
percona-xtrabackup
haveged
lsof
redhat-lsb-core
vim
rpm-build"

yum -y install ${packages}

chkconfig mysqld on
chkconfig haveged on

/etc/init.d/haveged start
