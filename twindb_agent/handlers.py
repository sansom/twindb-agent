# -*- coding: utf-8 -*-
import logging
import os
import subprocess
import sys
import twindb_agent.config
import twindb_agent.httpclient
import twindb_agent.gpg
import twindb_agent.twindb_mysql
import twindb_agent.api


def get_config():
    """
    Gets backup config from TwinDB dispatcher
    :return: Backup config or None if error happened
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger("twindb_remote")
    log.debug("Getting config for server_id = %s" % agent_config.server_id)

    api = twindb_agent.api.TwinDBAPI()
    data = {
        "type": "get_config",
        "params": {
            "server_id": agent_config.server_id
        }
    }
    config = api.call(data)
    return config


def get_job():
    """
    Gets job order from TwinDB dispatcher
    :return: Job order in python dictionary or None if error happened
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger("twindb_remote")
    log.debug("Getting job for server_id = %s" % agent_config.server_id)

    api = twindb_agent.api.TwinDBAPI()
    data = {
        "type": "get_job",
        "params": {}
    }
    job_order = api.call(data)
    return job_order


def is_registered():
    """
    Checks whether the server is registered or not
    :return: True if registered, False if not so much
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger("twindb_console")
    log.debug("Getting registration status for server_id = %s" % agent_config.server_id)

    twindb_email = "%s@twindb.com" % agent_config.server_id
    log.debug("Reading GPG public key of %s." % twindb_email)

    # Reading the GPG key
    gpg_cmd = ["gpg", "--homedir", agent_config.gpg_homedir, "--armor", "--export", twindb_email]
    try:
        p = subprocess.Popen(gpg_cmd, stdout=subprocess.PIPE)
        enc_public_key = p.communicate()[0]
    except OSError as err:
        log.error("Failed to run command %r. %s" % (gpg_cmd, err))
        log.error("Failed to export GPG keys of %s from %s." % (twindb_email, agent_config.gpg_homedir))
        sys.exit(2)

    # Call the TwinDB api to check for server registration
    data = {
        "type": "is_registered",
        "params": {
            "server_id": agent_config.server_id,
            "enc_public_key": enc_public_key
        }
    }
    api = twindb_agent.api.TwinDBAPI(logger_name="twindb_console")
    api_response = api.call(data)
    if api_response:
        if api_response["registered"]:
            return True
        else:
            return False
    else:
        # API call was unsuccessfull, consider the agent unregistered
        return False


def register(code):
    """
    Register this server in TwinDB dispatcher. Exits if error happened
    :param code: string with a secret registration code
    :return: True - if server was successfully registered
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger("twindb_console")

    # Check that the agent can connect to local MySQL
    mysql = twindb_agent.twindb_mysql.MySQL(logger_name="twindb_console")
    conn = mysql.get_mysql_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM information_schema.user_privileges")
        row = cursor.fetchone()
        if row[0] == 0:
            log.error("Local MySQL server is running with --skip-grant-tables option")
            return False
        conn.close()
    else:
        if not (agent_config.mysql_user or agent_config.mysql_password):
            log.info("Try to call the agent with -u and -p options to specify MySQL user and password")
            log.info("Another option is to specify MySQL user and password in /root/.my.cnf")
        sys.exit(2)
    # Check early to see that the MySQL user passed to the agent has enough
    # privileges to create a separate MySQL user needed by TwinDB
    mysql_access_available, missing_mysql_privileges = mysql.has_mysql_access()
    if not mysql_access_available:
        log.error("The MySQL user %s does not have enough privileges" % agent_config.mysql_user)
        if missing_mysql_privileges:
            log.error("Following privileges are missing: %s" % ','.join(missing_mysql_privileges))
        return False

    log.info("Registering TwinDB agent with code %s" % code)
    name = os.uname()[1].strip()  # un[1] is a hostname

    twindb_email = "%s@twindb.com" % agent_config.server_id

    # Read GPG public key
    cmd = ["gpg", "--homedir", agent_config.gpg_homedir, "--armor", "--export", twindb_email]
    try:
        log.debug("Reading GPG public key of %s." % twindb_email)
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        enc_public_key = p1.communicate()[0]
    except OSError as err:
        log.error("Failed to run command %r. %s" % (cmd, err))
        log.error("Failed to export GPG keys of %s from %s." % (twindb_email, agent_config.gpg_homedir))
        return False

    if not os.path.isfile(agent_config.ssh_private_key_file):
        try:
            log.info("Generating SSH keys pair.")
            subprocess.call(["ssh-keygen", "-N", "", "-f", agent_config.ssh_private_key_file])
        except OSError as err:
            log.error("Failed to run command %r. %s" % (cmd, err))
            log.error("Failed to generate SSH keys.")
            return False
    try:
        log.info("Reading SSH public key from %s." % agent_config.ssh_public_key_file)
        f = open(agent_config.ssh_public_key_file, 'r')
        ssh_public_key = f.read()
        f.close()
    except IOError as err:
        log.error("Failed to read from file %s. %s" % (agent_config.ssh_public_key_file, err))
        log.error("Failed to read SSH keys.")
        return False

    # Read local ip addresses
    cmd = "ip addr"
    cmd += "| grep -w inet"
    cmd += "| awk '{ print $2}'"
    cmd += "| awk -F/ '{ print $1}'"
    cout = None
    log.debug("Getting list of local IP addresses")
    try:
        log.debug("Running: %s" % cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        cout, cerr = p.communicate()
        log.debug("STDOUT: %s" % cout)
        log.debug("STDERR: %s" % cerr)
    except OSError as err:
        log.error("Failed to run command %r. %s" % (cmd, err))
    local_ip = list()
    for row in cout.split("\n"):
        row = row.rstrip("\n")
        if row and row != "127.0.0.1":
            local_ip.append(row)
    ss = mysql.get_slave_status()
    data = {
        "type": "register",
        "params": {
            "reg_code": code,
            "name": name,
            "server_id": agent_config.server_id,
            "enc_public_key": enc_public_key,
            "ssh_public_key": ssh_public_key,
            "mysql_server_id": ss["mysql_server_id"],
            "mysql_master_server_id": ss["mysql_master_server_id"],
            "mysql_master_host": ss["mysql_master_host"],
            "mysql_seconds_behind_master": ss["mysql_seconds_behind_master"],
            "mysql_slave_io_running": ss["mysql_slave_io_running"],
            "mysql_slave_sql_running": ss["mysql_slave_sql_running"],
            "local_ip": local_ip
        }
    }
    api = twindb_agent.api.TwinDBAPI()
    api.call(data)
    if api.success:
        log.info("Received successful response to register an agent")
        if mysql.create_agent_user():
            log.info("Created MySQL user for TwinDB agent")
            return True
        else:
            log.error("Failed to created MySQL user for TwinDB agent")
            return False
    else:
        log.error("Failed to register agent")
        log.error(api.error)
        log.debug(api.debug)


def commit_registration():
    """
    Confirms that agent successfully created local MySQL user.
    :return:
    """
    log = logging.getLogger("twindb_console")
    data = {
        "type": "confirm_registration",
        "params": {}
    }
    api = twindb_agent.api.TwinDBAPI()
    api.call(data)
    if api.success:
        log.info("Successfully confirmed agent registration")
        return True
    else:
        log.error("Failer to config agent registration")
        return False


def log_job_notify(params):
    """
    Notifies a job event to TwinDB dispatcher
    :param params: { event: "start_job", job_id: job_id } or
             { event: "stop_job", job_id: job_id, ret_code: ret }
    :return: True of False if error happened
    """
    log = logging.getLogger("twindb_remote")
    log.info("Sending event notification %s" % params["event"])
    data = {
        "type": "notify",
        "params": params
    }
    job_id = int(params["job_id"])
    api = twindb_agent.api.TwinDBAPI()
    api.call(data)
    if api.success:
        log.debug("Dispatcher acknowledged job_id = %d notification" % job_id)
        return True
    else:
        log.error("Dispatcher didn't acknowledge job_id = %d notification" % job_id)
        return False


def report_show_slave_status():
    """
    Reports slave status to TwinDB dispatcher
    :return: nothing
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger("twindb_remote")
    log.debug("Reporting SHOW SLAVE STATUS for server_id = %s" % agent_config.server_id)

    server_config = get_config()
    if not server_config:
        log.error("Failed to get server config from dispatcher")
        return
    mysql = twindb_agent.twindb_mysql.MySQL(mysql_user=server_config["mysql_user"],
                                            mysql_password=server_config["mysql_password"])
    ss = mysql.get_slave_status()
    data = {
        "type": "report_sss",
        "params": {
            "server_id": agent_config.server_id,
            "mysql_server_id": ss["mysql_server_id"],
            "mysql_master_server_id": ss["mysql_master_server_id"],
            "mysql_master_host": ss["mysql_master_host"],
            "mysql_seconds_behind_master": ss["mysql_seconds_behind_master"],
            "mysql_slave_io_running": ss["mysql_slave_io_running"],
            "mysql_slave_sql_running": ss["mysql_slave_sql_running"],
        }
    }
    api = twindb_agent.api.TwinDBAPI()
    api.call(data)
    if not api.success:
        log.error("Could not report replication status to the dispatcher")
    return


def report_agent_privileges():
    """
    Reports what privileges are given to the agent
    :return: nothing
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger("twindb_remote")
    log.debug("Reporting agent privileges for server_id = %s" % agent_config.server_id)

    server_config = get_config()
    if not server_config:
        log.error("Failed to get server config from dispatcher")
        return
    mysql = twindb_agent.twindb_mysql.MySQL(mysql_user=server_config["mysql_user"],
                                            mysql_password=server_config["mysql_password"])

    con = mysql.get_mysql_connection()
    cursor = con.cursor()
    query = "SELECT PRIVILEGE_TYPE FROM information_schema.USER_PRIVILEGES"
    log.debug("Sending query : %s" % query)
    cursor.execute(query)

    privileges = {
        "Reload_priv": "N",
        "Lock_tables_priv": "N",
        "Repl_client_priv": "N",
        "Super_priv": "N",
        "Create_tablespace_priv": "N"
    }
    for (priv,) in cursor:
        if priv == "RELOAD":
            privileges["Reload_priv"] = "Y"
        elif priv == "LOCK TABLES":
            privileges["Lock_tables_priv"] = "Y"
        elif priv == "REPLICATION CLIENT":
            privileges["Repl_client_priv"] = "Y"
        elif priv == "SUPER":
            privileges["Super_priv"] = "Y"
        elif priv == "CREATE TABLESPACE":
            privileges["Create_tablespace_priv"] = "Y"
    data = {
        "type": "report_agent_privileges",
        "params": {
            "Reload_priv": privileges["Reload_priv"],
            "Lock_tables_priv": privileges["Lock_tables_priv"],
            "Repl_client_priv": privileges["Repl_client_priv"],
            "Super_priv": privileges["Super_priv"],
            "Create_tablespace_priv": privileges["Create_tablespace_priv"]
        }
    }
    api = twindb_agent.api.TwinDBAPI()
    api.call(data)
    if not api.success:
        log.error("Could not report agent permissions to the dispatcher")
    return


def unregister(delete_backups=False):
    """
    Unregisters this server in TwinDB dispatcher
    Returns
      True    - if server was successfully unregistered
      False   - if error happened
    """
    log = logging.getLogger("twindb_console")

    data = {
        "type": "unregister",
        "params": {
            "delete_backups": delete_backups,
        }
    }
    api = twindb_agent.api.TwinDBAPI(logger_name="twindb_console")
    api.call(data)
    if api.success:
        log.info("The server is successfully unregistered")
    else:
        log.error("Failed to unregister the agent")
    return


def schedule_backup():
    """
    Asks dispatcher to schedule a job for this server
    """
    log = logging.getLogger("twindb_console")
    data = {
        "type": "schedule_backup",
        "params": {}
    }
    api = twindb_agent.api.TwinDBAPI()
    api.call(data)
    if api.success:
        log.info("A backup job is successfully registered")
        return True
    else:
        log.error("Failed to schedule a backup job")
        return False
