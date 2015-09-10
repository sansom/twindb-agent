#!/usr/bin/env bash

set -exu

function install_lsb_release() {
    if ! test -z "`which yum`"
    then
        # redhat-lsb provides lsb_release on CentOS 5
        # redhat-lsb-core provides lsb_release on CentOS 6 and 7
        yum -y install redhat-lsb-core redhat-lsb
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
    "CentOS"|"AmazonAMI")
        sed -i "s/HOSTNAME=localhost.localdomain/HOSTNAME=${hostname}/" /etc/sysconfig/network
        ;;
    "Ubuntu" | "Debian")
        echo "${hostname}" > /etc/hostname
        ;;
    *)
        echo "Unknown OS type ${dist_id}"
        lsb_release -a
        exit -1
esac
