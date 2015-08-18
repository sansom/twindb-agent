#!/usr/bin/env bash

mysql -u root -e "RESET SLAVE"
mysql -u root -e "CHANGE MASTER TO
    MASTER_HOST='192.168.50.101',
    MASTER_USER='replication',
    MASTER_PASSWORD='bigs3cret',
    MASTER_LOG_FILE='mysqld-bin.000001',
    MASTER_LOG_POS=120"
mysql -u root -e "START SLAVE"
