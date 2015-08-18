#!/usr/bin/env bash

set -e
export PATH=$PATH:/usr/sbin

function wait_for_mysql() {
    # wait till mysql starts
    timeout=300
    mysql_started="NO"
    while [ ${timeout} -gt 0 ]
    do
        if ! [ "`mysql -e 'SELECT 1'`" = "1" ]
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

/etc/init.d/mysqld start

if [ "`wait_for_mysql`" = "SUCCESS" ]
then
    exit 0
else
    echo "MySQL failed to start"
    exit -1
fi
