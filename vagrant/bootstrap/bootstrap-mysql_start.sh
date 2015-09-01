#!/usr/bin/env bash

set -exu
export PATH=$PATH:/usr/sbin

function wait_for_mysql() {
    # wait till mysql starts
    # $1 is an optional MySQL password
    timeout=300
    mysql_started="NO"
    MYSQL=mysql
    MYSQL_ARGS=""
    set +u
    if ! test -z "$1"
    then
        MYSQL_ARGS="${MYSQL_ARGS} -p$1"
    fi
    set -u
    while [ ${timeout} -gt 0 ]
    do
        if [ "`${MYSQL} ${MYSQL_ARGS} -NBe 'SELECT 1'`" = "1" ]
        then
            echo "SUCCESS"
            break
        fi
        sleep 1
        let timeout=$timeout-1
    done
}

release=`uname -r | awk -F. '{ print $4 }'`

if [ "$release" == "el5" ]
then
    useradd mysql --gid mysql --shell /sbin/nologin
    chown -R mysql:mysql /var/run/mysqld
fi

MYSQL_PASSWORD=""
dist_id=`lsb_release -is`
case "${dist_id}" in
    "CentOS")
        service mysqld start
        ;;
    "Ubuntu" | "Debian")
        MYSQL_PASSWORD="MySuperPassword"
        service mysql restart
        ;;
    *)
        echo "Unknown OS type ${dist_id}"
        lsb_release -a
        exit -1
esac

if [ "`wait_for_mysql ${MYSQL_PASSWORD}`" = "SUCCESS" ]
then
    exit 0
else
    echo "MySQL failed to start"
    exit -1
fi
