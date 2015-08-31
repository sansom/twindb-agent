#!/usr/bin/env bash

set -exu

mysql -u root -e "RESET MASTER"
mysql -u root -e "CREATE USER 'replication'@'%' IDENTIFIED BY 'bigs3cret'"
mysql -u root -e "GRANT REPLICATION SLAVE ON *.* TO 'replication'@'%'"
