#!/usr/bin/env bash

set -e

hostname="`hostname`"
echo "127.0.0.1         ${hostname}" >> /etc/hosts
sed -i "s/HOSTNAME=localhost.localdomain/HOSTNAME=${hostname}/" /etc/sysconfig/network
