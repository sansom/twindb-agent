#!/usr/bin/env bash

set -e

hostname="`hostname`"
idx=`hostname | sed 's/[a-z]//g'`

cat <<EOF > /etc/my.cnf
[mysqld]
server_id=1${idx}
log_bin=mysqld-bin
EOF
