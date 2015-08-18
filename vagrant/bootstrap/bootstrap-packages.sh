#!/usr/bin/env bash

set -ex
export PATH=$PATH:/sbin

function install_packages_centos() {
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

    case ${release} in
        "el5")
            ;;
        "el6")
            chkconfig haveged on
            /etc/init.d/haveged start
            ;;
        "el7")
            chkconfig haveged on
            service haveged start
            ;;
    esac
}

function install_packages_debian() {
    echo "Installing Debian packages"
    export DEBIAN_FRONTEND=noninteractive
    debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-server string mysql-5.6'
    # debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-workbench string workbench-6.3'
    debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-utilities string mysql-utilities-1.5'
    debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-connector-python string connector-python-2.0'
    debconf-set-selections <<< 'mysql-server mysql-server/root_password password MySuperPassword'
    debconf-set-selections <<< 'mysql-server mysql-server/root_password_again password MySuperPassword'

    codename=`lsb_release -cs`

    # MySQL repo
    case "${codename}" in
        "wheezy")
            apt_config_deb="mysql-apt-config_0.3.5-1debian7_all.deb"
            ;;
        "jessie")
            apt_config_deb="mysql-apt-config_0.3.6-1debian8_all.deb"
            ;;
        "precise")
            apt_config_deb="mysql-apt-config_0.3.5-1ubuntu12.04_all.deb"
            ;;
        "trusty")
            apt_config_deb="mysql-apt-config_0.3.5-1ubuntu14.04_all.deb"
            ;;
        *)
            echo "Unknown OS type ${dist_id}"
            lsb_release -a
            exit -1
    esac
    wget -q -O /tmp/${apt_config_deb} https://dev.mysql.com/get/${apt_config_deb}
    dpkg -i /tmp/${apt_config_deb}

    # TwinDB repo
    # we don't have TwinDB repo for jessie yet
    # TODO https://bugs.launchpad.net/twindb-agent/+bug/1486261
    if [ "${codename}" != "jessie" ]
    then
        wget -qO /etc/apt/sources.list.d/twindb.list http://repo.twindb.com/twindb.`lsb_release -cs`.list
        apt-key adv --keyserver pgp.mit.edu --recv-keys 2A9C65370E199794
    fi

    apt-get update

    packages="
    mysql-server
    mysql-connector-python
    percona-xtrabackup
    haveged
    lsof
    vim
    chkconfig"
    apt-get -y install ${packages}
}


dist_id=`lsb_release -is`
case "${dist_id}" in
    "CentOS")
        install_packages_centos
        ;;
    "Ubuntu" | "Debian")
        install_packages_debian
        ;;
    *)
        echo "Unknown OS type ${dist_id}"
        lsb_release -a
        exit -1
esac


