#!/usr/bin/env bash

set -exu

MYSQL_ARGS="-u root"
MYSQL_PASSWORD=""
dist_id=`lsb_release -is`
case "${dist_id}" in
    "CentOS")
        ;;
    "Ubuntu" | "Debian")
        MYSQL_PASSWORD="MySuperPassword"
        MYSQL_ARGS="-u root -p${MYSQL_PASSWORD}"
        ;;
    *)
        echo "Unknown OS type ${dist_id}"
        lsb_release -a
        exit -1
esac


mysql ${MYSQL_ARGS} -e "RESET MASTER"
mysql ${MYSQL_ARGS} -e "CREATE USER 'replication'@'%' IDENTIFIED BY 'bigs3cret'"
mysql ${MYSQL_ARGS} -e "GRANT REPLICATION SLAVE ON *.* TO 'replication'@'%'"
