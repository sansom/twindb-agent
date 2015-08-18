#!/usr/bin/env bash

set -e

function install_lsb_release() {
    if ! test -z "`which yum`"
    then
        yum -y install redhat-lsb-core
    fi
    if ! test -z "`which apt-get`"
    then
        apt-get -y install lsb_release
    fi
}

hostname="`hostname`"
echo "127.0.0.1         ${hostname}" >> /etc/hosts

if test -z "`which lsb_release`"
then
    install_lsb_release
fi

dist_id=`lsb_release -is`
case "${dist_id}" in
    "CentOS")
        sed -i "s/HOSTNAME=localhost.localdomain/HOSTNAME=${hostname}/" /etc/sysconfig/network
        ;;
    "Ubuntu")
        ;;
    "Debian")
        ;;
    *)
        echo "Unknown OS type ${dist_id}"
        lsb_release -a
        exit -1
esac
