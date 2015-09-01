#!/usr/bin/env bash

set -exu
export PATH=$PATH:/sbin

function get_epel_rpm() {
    release=$1

    case ${release} in
        "el5")
            echo "https://dl.fedoraproject.org/pub/epel/epel-release-latest-5.noarch.rpm"
            ;;
        "el6")
            echo "https://dl.fedoraproject.org/pub/epel/epel-release-latest-6.noarch.rpm"
            ;;
        "el7")
            echo "https://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm"
            ;;
    esac
}

function get_oracle_rpm() {
    release=$1

    case ${release} in
        "el5")
            echo "http://dev.mysql.com/get/mysql-community-release-el5-5.noarch.rpm"
            ;;
        "el6")
            echo "http://dev.mysql.com/get/mysql-community-release-el6-5.noarch.rpm"
            ;;
        "el7")
            echo "http://dev.mysql.com/get/mysql-community-release-el7-5.noarch.rpm"
            ;;
    esac
}


function install_packages_centos() {

    release=`uname -r | awk -F. '{ print $4 }'`

    # TwinDB repo
    curl -s https://packagecloud.io/install/repositories/twindb/main/script.rpm.sh | bash

    # EPEL repo
    wget -O /tmp/epel.rpm `get_epel_rpm ${release}`
    rpm -Uhv /tmp/epel.rpm

    # Oracle repo
    wget -O /tmp/oracle.rpm `get_oracle_rpm ${release}`
    rpm -Uhv /tmp/oracle.rpm

    packages="
    mysql-server
    mysql-connector-python
    percona-xtrabackup
    haveged
    lsof
    redhat-lsb-core
    vim
    rpm-build
    chkconfig"

    for i in `seq 3`
    do
        yum -y --disablerepo=mysql-connectors-community install ${packages} && break
    done

    case ${release} in
        "el5")
            chkconfig mysqld on
            ;;
        "el6")
            chkconfig mysqld on
            chkconfig haveged on
            service haveged start
            ;;
        "el7")
            chkconfig mysqld on
            chkconfig haveged on
            service haveged start
            ;;
    esac
}

function install_packages_debian() {
    echo "Installing Debian packages"
    export DEBIAN_FRONTEND=noninteractive
    # debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-server string mysql-5.6'
    # debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-workbench string workbench-6.3'
    # debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-utilities string mysql-utilities-1.5'
    # debconf-set-selections <<< 'mysql-apt-config mysql-apt-config/select-connector-python string connector-python-2.0'
    debconf-set-selections <<< 'mysql-server mysql-server/root_password password MySuperPassword'
    debconf-set-selections <<< 'mysql-server mysql-server/root_password_again password MySuperPassword'

    apt-get update
    # We need it for packagecloud repo
    apt-get -y install apt-transport-https curl

    packages="
    mysql-server
    mysql-connector-python
    percona-xtrabackup
    haveged
    lsof
    vim
    build-essential
    devscripts
    debhelper"
    codename=`lsb_release -cs`

    case "${codename}" in
        "wheezy")
            packages="${packages} chkconfig"
            ;;
        "jessie")
            packages="${packages} chkconfig"
            ;;
        "precise")
            packages="${packages} chkconfig"
            ;;
        "trusty")
            packages="${packages} sysv-rc-conf"
            ;;
        *)
            echo "Unknown OS type ${dist_id}"
            lsb_release -a
            exit -1
    esac

    # TwinDB repo
    curl -s https://packagecloud.io/install/repositories/twindb/main/script.deb.sh | sudo bash


    # Try to update APT repos up to 5 times
    for i in `seq 5`
    do
        apt-get update && break
        echo "Failed to update apt repos. Retrying"
    done

    # Try to update APT repos up to 5 times
    for i in `seq 5`
    do
        apt-get -y install ${packages} && break
        echo "Failed to install packages. Retrying"
    done


    case "${codename}" in
        "wheezy" | "jessie" | "precise")
            test -f /sbin/insserv || ln -s /usr/lib/insserv/insserv /sbin/insserv
            chkconfig mysql on
            chkconfig haveged on
            ;;
        "trusty")
            sysv-rc-conf mysql on
            sysv-rc-conf haveged on
            ;;
        *)
            echo "Unknown OS type ${dist_id}"
            lsb_release -a
            exit -1
    esac

    service haveged start

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


