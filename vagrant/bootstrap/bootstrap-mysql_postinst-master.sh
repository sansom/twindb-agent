#!/usr/bin/env bash

mysql -u root -e "RESET MASTER"
mysql -u root -e "CREATE USER 'replication'@'%' IDENTIFIED BY 'bigs3cret'"
mysql -u root -e "GRANT REPLICATION SLAVE ON *.* TO 'replication'@'%'"
