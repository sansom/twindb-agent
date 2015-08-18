#!/usr/bin/env bash

set -e

hostname="`hostname`"
idx=`hostname | sed 's/[a-z]//g'`

dist_id=`lsb_release -is`
case "${dist_id}" in
    "CentOS")
        mysql_config_file="/etc/my.cnf"
        ;;
    "Ubuntu"|"Debian")
        mysql_config_file="/etc/mysql/my.cnf"
        ;;
    *)
        echo "Unknown OS type ${dist_id}"
        lsb_release -a
        exit -1
esac

cat <<EOF > "${mysql_config_file}"
[mysqld]
server_id=1${idx}
log_bin=mysqld-bin
EOF
