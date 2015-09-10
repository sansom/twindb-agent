#!/usr/bin/env bash

set -exu
MYSQL_ARGS="-u root"
MYSQL_PASSWORD=""
dist_id=`lsb_release -is`
case "${dist_id}" in
    "CentOS"|"AmazonAMI")
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

mysql ${MYSQL_ARGS} -e "RESET SLAVE"
mysql ${MYSQL_ARGS} -e "CHANGE MASTER TO
    MASTER_HOST='192.168.50.101',
    MASTER_USER='replication',
    MASTER_PASSWORD='bigs3cret',
    MASTER_LOG_FILE='mysqld-bin.000001',
    MASTER_LOG_POS=120"
mysql ${MYSQL_ARGS} -e "START SLAVE"
