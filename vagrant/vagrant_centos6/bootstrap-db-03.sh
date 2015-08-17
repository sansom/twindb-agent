#!/usr/bin/env bash

set -e

hostname="db03"

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

echo "127.0.0.1         ${hostname}" >> /etc/hosts
# echo "192.168.50.100    dispatcher.twindb.com" >> /etc/hosts
# echo "192.168.50.100    console.dev.twindb.com" >> /etc/hosts

chkconfig mysqld on
chkconfig haveged on

/etc/init.d/haveged start

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
cat <<EOF > /etc/my.cnf
[mysqld]
server_id=103
log_bin=mysqld-bin
EOF

/etc/init.d/mysqld start

if [ "`wait_for_mysql`" = "SUCCESS" ]
then
    mysql -u root -e "RESET MASTER"
    mysql -u root -e "CHANGE MASTER TO
        MASTER_HOST='192.168.50.101',
        MASTER_USER='replication',
        MASTER_PASSWORD='bigs3cret',
        MASTER_LOG_FILE='mysqld-bin.000001',
        MASTER_LOG_POS=120"
    mysql -u root -e "START SLAVE"
else
    echo "MySQL failed to start"
    exit -1
fi

sed -i "s/HOSTNAME=localhost.localdomain/HOSTNAME=${hostname}/" /etc/sysconfig/network
hostname ${hostname}
