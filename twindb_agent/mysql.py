"""
Classes and funtions to work with MySQL
"""
import ConfigParser
import getpass
import os
import subprocess
import pwd
import twindb.logging_remote
import twindb.globals

try:
    import mysql.connector
except ImportError:
    # On CentOS 5 mysql.connector is in python 2.6 directory
    import sys
    sys.path.insert(0, '/usr/lib/python2.6/site-packages')
    import mysql.connector


class MySQL(object):
    def __init__(self, server_id, user=None, passwd=None, debug=False):
        self.server_id = server_id
        self.user = user
        self.passwd = passwd
        self.logger = twindb.logging_remote.getlogger(__name__, server_id, debug=debug)

    def get_mysql_connection(self):
        """
        Returns connection to the local MySQL instance.
        If user is passed as an argument it'll be used to connect,
        otherwise the second choice will be to use mysql_user.
        If neither user names are set the function will try to use either of MySQL option files
        (/etc/my.cnf, /etc/mysql/my.cnf, or /root/.my.cnf). If the option files don't exist
        it'll try to connect as root w/o password.
        """
        log = self.logger
        try:

            unix_socket = self.get_unix_socket()
            if not self.user:
                if twindb.globals.mysql_user or twindb.globals.mysql_password:
                    log.debug('Using MySQL user specified in the command line')
                    if twindb.globals.mysql_user:
                        self.user = twindb.globals.mysql_user
                    else:
                        self.user = getpass.getuser()
                    self.passwd = twindb.globals.mysql_password
                else:
                    for options_file in ["/etc/my.cnf", "/etc/mysql/my.cnf", "/usr/etc/my.cnf",
                                         "/root/.my.cnf", "/root/.mylogin.cnf"]:
                        if os.path.exists(options_file):
                            try:
                                config = ConfigParser.ConfigParser()
                                config.read(options_file)
                                for section in ["client", "twindb"]:
                                    if config.has_section(section):
                                        if config.has_option(section, "user"):
                                            user = config.get(section, "user")
                                        if config.has_option(section, "password"):
                                            passwd = config.get(section, "user")
                            except ConfigParser.ParsingError as err:
                                log.debug(err)
                                log.debug("Ignoring options file %s" % options_file)
                                pass
                    # If user isn't set by the function argument, global mysql_user
                    # or MySQL options file connect as unix user w/ empty password
                    if not self.user:
                        self.user = pwd.getpwuid(os.getuid()).pw_name
                        self.passwd = ""
                        log.debug("Connecting to MySQL as unix user %s" % self.user)
            conn = mysql.connector.connect(user=self.user, passwd=self.passwd, unix_socket=unix_socket)
            log.debug("Connected to MySQL as %s@localhost " % conn.user)
        except mysql.connector.Error as err:
            log.error("Can not connect to local MySQL server")
            log.error("MySQL said: %s" % err.msg)
            return None
        return conn

    def get_unix_socket(self):
        """
        Finds MySQL socket
        :return: path to unix socket or None if not found
        """
        log = self.logger
        cmd = ["lsof", "-U", "-c", "/^mysqld$/", "-a", "-F", "n"]
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cout, cerr = p.communicate()
            # Outputs socket in format
            # # lsof -U -c mysqld -a -F n
            # p11029
            # n/var/lib/mysql/mysql.sock
            mysql_socket = cout.split()[1][1:]
            if not os.path.exists(mysql_socket):
                return None
        except OSError as err:
            log.error("Failed to run command %r. %s" % (cmd, err))
            return None
        return mysql_socket

    def get_slave_status(self):
        """
        Reads SHOW SLAVE STATUS from the local server
        :return: dictionary with SHOW SLAVE STATUS result
        """
        log = self.logger
        conn = self.get_mysql_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
        else:
            return None
        result = {
            "mysql_server_id": None,
            "mysql_master_server_id": None,
            "mysql_master_host": None,
            "mysql_seconds_behind_master": None,
            "mysql_slave_io_running": None,
            "mysql_slave_sql_running": None
        }
        try:
            cursor.execute("SHOW SLAVE STATUS")
            for row in cursor:
                result["mysql_master_server_id"] = row["Master_Server_Id"]
                result["mysql_master_host"] = row["Master_Host"]
                result["mysql_seconds_behind_master"] = row["Seconds_Behind_Master"]
                result["mysql_slave_io_running"] = row["Slave_IO_Running"]
                result["mysql_slave_sql_running"] = row["Slave_SQL_Running"]
        except mysql.connector.Error as err:
            log.error("Could get SHOW SLAVE STATUS")
            log.error("MySQL Error: " % err)
            return None
        try:
            cursor.execute("SELECT @@server_id AS server_id")
            for row in cursor:
                result["mysql_server_id"] = row["server_id"]
            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            log.error("Could not read server_id")
            log.error("MySQL Error: " % err)
            return None
        return result

    def has_mysql_access(self, grant_capability=True):
        """
        Reports if a user has all required MySQL privileges
        :param grant_capability: TODO to add description
        :return: a pair of a boolean that tells whether MySQL user has all required privileges
        and a list of missing privileges
        """
        log = self.logger
        has_required_grants = False

        # list of missing privileges
        missing_privileges = []
        required_privileges = ['RELOAD', 'SUPER', 'LOCK TABLES', 'REPLICATION CLIENT', 'CREATE TABLESPACE']

        try:
            conn = self.get_mysql_connection()

            if isinstance(conn, mysql.connector.MySQLConnection):
                cursor = conn.cursor(dictionary=True)
            else:
                missing_privileges = required_privileges
                return has_required_grants, missing_privileges

            # Fetch the current user and matching host part as it could either be
            # connecting using localhost or using '%'
            cursor.execute("SELECT CURRENT_USER() as curr_user")
            row = cursor.fetchone()
            username, hostname = row['curr_user'].split('@')

            quoted_privileges = ','.join("'%s'" % item for item in required_privileges)

            sql = ("SELECT privilege_type, is_grantable FROM information_schema.user_privileges "
                   "WHERE grantee=\"'%s'@'%s'\" AND privilege_type IN (%s)" % (username, hostname, quoted_privileges))
            cursor.execute(sql)

            user_privileges = []
            grantable_privileges = []
            for row in cursor:
                user_privileges.append(row[u'privilege_type'])
                if row[u'is_grantable'] == 'YES':
                    grantable_privileges.append(row[u'privilege_type'])

            # Check that the user has all the required grants
            has_required_grants = True
            for privilege in required_privileges:
                if privilege in user_privileges:
                    # If the user should also be able to grant the privilege then we check for the grant capability too
                    # We consider the privilege not available if its not grantable in such a case
                    if grant_capability and privilege not in grantable_privileges:
                        has_required_grants = False
                else:
                    has_required_grants = False
                    missing_privileges.append(privilege)

            if len(missing_privileges) < 1 and grant_capability:
                required_privileges = ['INSERT', 'UPDATE']
                quoted_privileges = ','.join("'%s'" % item for item in required_privileges)

                # If the user should be able to grant privileges too, such as the user that is used to create the
                # twindb_agent user then, insert and update privileges are needed on mysql.*
                sql = ("SELECT privilege_type FROM information_schema.schema_privileges "
                       "WHERE grantee=\"'%s'@'%s'\" AND table_schema = 'mysql' AND privilege_type IN (%s)"
                       "UNION "
                       "SELECT privilege_type FROM information_schema.user_privileges "
                       "WHERE grantee=\"'%s'@'%s'\" AND privilege_type IN (%s)"
                       % (username, hostname, quoted_privileges, username, hostname, quoted_privileges))
                cursor.execute(sql)

                user_privileges = []
                for row in cursor:
                    user_privileges.append(row[u'privilege_type'])

                for privilege in required_privileges:
                    if privilege not in user_privileges:
                        has_required_grants = False
                        break

            cursor.close()
            conn.close()
        except mysql.connector.Error as err:
            log.error("Could not read the grants information from MySQL")
            log.error("MySQL Error: %s" % err)
        return has_required_grants, missing_privileges
