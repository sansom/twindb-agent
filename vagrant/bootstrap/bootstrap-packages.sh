#!/usr/bin/env bash

set -e
export PATH=$PATH:/sbin

release=`uname -r | awk -F. '{ print $4 }'`
yum -y install https://repo.twindb.com/twindb-release-latest.noarch.rpm

case ${release} in
    "el5")
        wget -O /tmp/mysql-community-release-el5-5.noarch.rpm --no-check-certificate \
            https://dev.mysql.com/get/mysql-community-release-el5-5.noarch.rpm
        rpm -Uhv /tmp/mysql-community-release-el5-5.noarch.rpm
        rpm -Uvh http://mirror.redsox.cc/pub/epel/5/x86_64/epel-release-5-4.noarch.rpm
        ;;
    "el6")
        yum -y install https://dev.mysql.com/get/mysql-community-release-el6-5.noarch.rpm
        rpm -Uvh http://mirror.redsox.cc/pub/epel/6/x86_64/epel-release-6-8.noarch.rpm
        ;;
    "el7")
        yum -y install https://dev.mysql.com/get/mysql-community-release-el7-5.noarch.rpm
        rpm -Uvh http://mirror.redsox.cc/pub/epel/7/x86_64/e/epel-release-7-5.noarch.rpm
        ;;
esac

packages="
mysql-community-server
mysql-connector-python
percona-xtrabackup
haveged
lsof
redhat-lsb-core
vim
rpm-build
chkconfig"

yum -y install ${packages}

chkconfig mysqld on

if [ "${release}" != "el5" ]
then
    chkconfig haveged on
    /etc/init.d/haveged start
fi
