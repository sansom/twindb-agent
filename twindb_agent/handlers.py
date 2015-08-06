# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
from datetime import datetime
import tempfile
import twindb_agent.httpclient
import twindb_agent.gpg
import twindb_agent.logging_remote
import twindb_agent.twindb_mysql
from twindb_agent.utils import exit_on_error


def get_config(agent_config, debug=False):
    """
    Gets backup config from TwinDB dispatcher
    :return: Backup config or None if error happened
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config.server_id, debug=debug)
    log.debug("Getting config for server_id = %s" % agent_config.server_id)
    response_body = "Empty response"
    config = None
    try:
        data = {
            "type": "get_config",
            "params": {
                "server_id": agent_config.server_id
            }
        }
        http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)
        response_body = http.get_response(data)
        if not response_body:
            return None
        d = json.JSONDecoder()
        response_body_decoded = d.decode(response_body)
        if response_body_decoded:
            gpg = twindb_agent.gpg.TwinDBGPG(agent_config)
            msg_decrypted = gpg.decrypt(response_body_decoded["response"])
            msg_pt = d.decode(msg_decrypted)
            config = msg_pt["data"]
            log.debug("Got config:\n%s" % json.dumps(twindb_agent.utils.sanitize_config(config),
                                                     indent=4, sort_keys=True))
            if msg_pt["error"]:
                log.error(msg_pt["error"])
    except KeyError as err:
        log.error("Failed to decode %s" % response_body)
        log.error(err)
        return None
    return config


def get_job(agent_config, debug=False):
    """
    Gets job order from TwinDB dispatcher
    :return: Job order in python dictionary or None if error happened
    """
    server_id = agent_config.server_id
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    job = None
    log.debug("Getting job for server_id = %s" % server_id)
    try:
        d = json.JSONDecoder()
        data = {
            "type": "get_job",
            "params": {}
        }
        http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)
        gpg = twindb_agent.gpg.TwinDBGPG(agent_config, debug=debug)
        response_body = http.get_response(data)
        if not response_body:
            log.error("Empty response from dispatcher")
            return None
        try:
            response_body_decoded = d.decode(response_body)
        except ValueError as err:
            log.error(err)
            return None
        if "response" not in response_body_decoded:
            log.error("There is no 'response' key in the response from dispatcher")
            return None
        if "success" not in response_body_decoded:
            log.error("There is no 'success' key in the response from dispatcher")
            return None
        msg_enc = response_body_decoded["response"]
        if response_body_decoded["success"]:

            job_json = gpg.decrypt(msg_enc)
            log.debug("job_json = %s" % job_json)
            if "data" not in job_json:
                log.error("There is no 'data' in decrypted response %s" % job_json)
                return None
            job = d.decode(job_json)["data"]
            if job and "params" in job and job["params"]:
                job["params"] = d.decode(job["params"])
                log.debug("Got job:\n%s" % json.dumps(job, indent=4, sort_keys=True))
        else:
            log.error("Couldn't get job")
            job_json = gpg.decrypt(msg_enc)
            log.error("Server said: %s" % d.decode(job_json)["error"])
    except TypeError as err:
        log.error("Failed to get a job: %s" % err)
        return None
    return job


def is_registered(agent_config, debug=False):
    """
    Checks whether the server is registered or not
    :return: True if registered, False if not so much
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    log.debug("Getting registration status for server_id = %s" % agent_config.server_id)

    twindb_email = "%s@twindb.com" % agent_config.server_id
    log.debug("Reading GPG public key of %s." % twindb_email)

    enc_public_key = None
    # Reading the GPG key
    gpg_cmd = ["gpg", "--homedir", agent_config.gpg_homedir, "--armor", "--export", twindb_email]
    try:
        p = subprocess.Popen(gpg_cmd, stdout=subprocess.PIPE)
        enc_public_key = p.communicate()[0]
    except OSError as err:
        log.error("Failed to run command %r. %s" % (gpg_cmd, err))
        exit_on_error("Failed to export GPG keys of %s from %s." % (twindb_email, agent_config.gpg_homedir))

    # Call the TwinDB api to check for server registration
    response_body = None
    try:
        data = {
            "type": "is_registered",
            "params": {
                "server_id": agent_config.server_id,
                "enc_public_key": enc_public_key
            }
        }
        http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)
        gpg = twindb_agent.gpg.TwinDBGPG(agent_config, debug=debug)
        response_body = http.get_response(data)
        if not response_body:
            return False
        json_decoder = json.JSONDecoder()
        response_body_decoded = json_decoder.decode(response_body)
        if response_body_decoded:
            if "response" in response_body_decoded:
                msg_decrypted = gpg.decrypt(response_body_decoded["response"])
                if msg_decrypted is None:
                    log.debug("No valid response from dispatcher. Consider agent unregistered")
                    return False
                msg_pt = json_decoder.decode(msg_decrypted)
                registration_status = msg_pt["data"]
                log.debug("Got registration status:\n%s" % json.dumps(registration_status, indent=4, sort_keys=True))
                if msg_pt["error"]:
                    log.error(msg_pt["error"])
                    exit_on_error(msg_pt["error"])
                return registration_status["registered"]
            else:
                log.debug("No valid response from dispatcher. Consider agent unregistered")
                return False
    except ValueError:
        log.debug("No valid JSON response from dispatcher. Consider agent unregistered")
        return False
    except KeyError as err:
        exit_on_error("Failed to decode response from dispatcher: %s. %s" % (response_body, err))
    return False


def register(code, agent_config, debug=False):
    """
    Registers this server in TwinDB dispatcher
    Inputs
      code    - string with secret registration code
    Returns
      True    - if server was successfully registered
    Exits if error happened
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, log_to_console=True, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)
    gpg = twindb_agent.gpg.TwinDBGPG(agent_config, debug=debug)

    # Check that the agent can connect to local MySQL
    mysql = twindb_agent.twindb_mysql.MySQL(agent_config, debug=debug)
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
    enc_public_key = None
    cmd = ["gpg", "--homedir", agent_config.gpg_homedir, "--armor", "--export", twindb_email]
    try:
        log.debug("Reading GPG public key of %s." % twindb_email)
        p1 = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        enc_public_key = p1.communicate()[0]
    except OSError as err:
        log.error("Failed to run command %r. %s" % (cmd, err))
        exit_on_error("Failed to export GPG keys of %s from %s." % (twindb_email, agent_config.gpg_homedir))

    if not os.path.isfile(agent_config.ssh_private_key_file):
        try:
            log.info("Generating SSH keys pair.")
            subprocess.call(["ssh-keygen", "-N", "", "-f", agent_config.ssh_private_key_file])
        except OSError as err:
            log.error("Failed to run command %r. %s" % (cmd, err))
            exit_on_error("Failed to generate SSH keys.")
    ssh_public_key = None
    try:
        log.info("Reading SSH public key from %s." % agent_config.ssh_public_key_file)
        f = open(agent_config.ssh_public_key_file, 'r')
        ssh_public_key = f.read()
        f.close()
    except IOError as err:
        log.error("Failed to read from file %s. %s" % (agent_config.ssh_public_key_file, err))
        exit_on_error("Failed to read SSH keys.")

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
    api_response = http.get_response(data)
    if api_response:
        json_decoder = json.JSONDecoder()
        response_decoded = json_decoder.decode(api_response)
        log.debug(response_decoded)

        error_msg = "Unknown error"
        if response_decoded["success"]:
            log.info("Received successful response to register an agent")
            mysql.create_agent_user()
        else:
            if "response" in response_decoded:
                msg_decrypted = gpg.decrypt(response_decoded["response"])
                if msg_decrypted is not None:
                    error_msg = json_decoder.decode(msg_decrypted)["error"]
            elif "errors" in response_decoded:
                error_msg = response_decoded["errors"]["msg"]

            exit_on_error("Failed to register the agent: %s" % error_msg)
    else:
        exit_on_error("Empty response from server")
    return True


def commit_registration(agent_config, debug=False):
    """
    Confirms that agent successfully created local MySQL user.
    :return:
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)
    gpg = twindb_agent.gpg.TwinDBGPG(agent_config, debug=debug)

    data = {
        "type": "confirm_registration",
        "params": {}
    }
    api_response = http.get_response(data)
    if api_response:
        json_decoder = json.JSONDecoder()
        response_decoded = json_decoder.decode(api_response)
        log.debug(response_decoded)

        error_msg = "Unknown error"
        if response_decoded["success"]:
            log.info("Successfully confirmed agent registration")
        else:
            if "response" in response_decoded:
                msg_decrypted = gpg.decrypt(response_decoded["response"])
                if msg_decrypted is not None:
                    error_msg = json_decoder.decode(msg_decrypted)["error"]
            elif "errors" in response_decoded:
                error_msg = response_decoded["errors"]["msg"]

            exit_on_error("Failed to register the agent: %s" % error_msg)
    else:
        exit_on_error("Empty response from server")
    return True


def log_job_notify(agent_config, params, debug=False):
    """
    Notifies a job event to TwinDB dispatcher
    :param params: { event: "start_job", job_id: job_id } or
             { event: "stop_job", job_id: job_id, ret_code: ret }
    :return: True of False if error happened
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)

    log.info("Sending event notification %s" % params["event"])
    data = {
        "type": "notify",
        "params": params
    }
    job_id = int(params["job_id"])
    response_body = http.get_response(data)
    if not response_body:
        log.error("Failed to notify status of job_id = %d to dispatcher" % job_id)
        return
    d = json.JSONDecoder()
    response_body_decoded = d.decode(response_body)
    if response_body_decoded["success"]:
        log.debug("Dispatcher acknowledged job_id = %d notification" % job_id)
        result = True
    else:
        log.error("Dispatcher didn't acknowledge job_id = %d notification" % job_id)
        result = False
    return result


def report_sss(agent_config, debug=False):
    """
    Reports slave status to TwinDB dispatcher
    :param agent_config:
    :return: nothing
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)

    log.debug("Reporting SHOW SLAVE STATUS for server_id = %s" % agent_config.server_id)

    server_config = get_config(agent_config)
    if not server_config:
        log.error("Failed to get server config from dispatcher")
        return
    mysql = twindb_agent.twindb_mysql.MySQL(agent_config,
                                            mysql_user=server_config["mysql_user"],
                                            mysql_password=server_config["mysql_password"],
                                            debug=debug)
    ss = mysql.get_slave_status()
    try:
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
        http.get_response(data)
    except TypeError as err:
        log.error("Could not report replication status to the dispatcher")
        log.error(err)
    return


def report_agent_privileges(agent_config, debug=False):
    """
    Reports what privileges are given to the agent
    :param agent_config:
    :return: nothing
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)

    log.debug("Reporting agent privileges for server_id = %s" % agent_config.server_id)

    server_config = get_config(agent_config)
    if not server_config:
        log.error("Failed to get server config from dispatcher")
        return
    mysql = twindb_agent.twindb_mysql.MySQL(agent_config,
                                            mysql_user=server_config["mysql_user"],
                                            mysql_password=server_config["mysql_password"],
                                            debug=debug)

    try:
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
        http.get_response(data)
    except AttributeError as err:
        log.error("Could not report agent permissions to the dispatcher")
        log.error(err)
    return


def send_key(agent_config, job_order, debug=False):
    """
    Processes send_key job
    :param agent_config:
    :return: nothing
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)

    # Get owner of the GPG key
    cmd_1 = ["gpg", "--list-packets"]
    try:
        gpg_pub_key = job_order["params"]["gpg_pub_key"]
        if gpg_pub_key:
            log.debug("Starting %r" % cmd_1)
            p1 = subprocess.Popen(cmd_1, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            cout, cerr = p1.communicate(gpg_pub_key)
            keyid = "Unknown"
            for line in cout.split("\n"):
                if "keyid:" in line:
                    keyid = line.replace("keyid:", "").strip()
                    break
            log.debug("Requestor's public key id is %s" % keyid)
        else:
            log.error("Requestor public key is empty")
            return -1
    except OSError as err:
        log.error("Failed to run command %r: %s" % (cmd_1, err))
        return -1
    # Import public GPG key. It's a user public key sent by the dispatcher
    try:
        log.debug("Importing requestor's key %s" % keyid)
        cmd_1 = ["gpg", "--import"]
        p1 = subprocess.Popen(cmd_1, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        cout, cerr = p1.communicate(gpg_pub_key)
        if cout:
            log.info(cout)
        if cerr:
            log.error(cerr)
    except OSError as err:
        log.error("Failed to run command %r: %s" % (cmd_1, err))
        return -1
    # Get private key and encrypt it
    gpg_pub_key = job_order["params"]["gpg_pub_key"]
    if gpg_pub_key:
        log.debug("Exporting private key of server %s" % agent_config.server_id)
        cmd_1 = ["gpg", "--armor", "--export-secret-key", agent_config.server_id]
        cmd_2 = ["gpg", "--armor", "--encrypt", "--sign", "--batch", "-r", keyid,
                 "--local-user", agent_config.server_id,
                 "--trust-model", "always"]
        try:
            log.debug("Starting %r" % cmd_1)
            p1 = subprocess.Popen(cmd_1, stdout=subprocess.PIPE)
        except OSError as err:
            log.error("Failed to run command %r: %s" % (cmd_1, err))
            return -1
        try:
            log.debug("Starting %r" % cmd_2)
            p2 = subprocess.Popen(cmd_2, stdin=p1.stdout, stdout=subprocess.PIPE)
            cout, cerr = p2.communicate()
            enc_private_key = cout
            log.debug("Encrypted private key %s" % enc_private_key)
        except OSError as err:
            log.error("Failed to run command %r: %s" % (cmd_2, err))
            return -1
        # Now send the private key to dispatcher
        data = {
            "type": "send_key",
            "params": {
                "enc_private_key": enc_private_key,
                "job_id": job_order["job_id"]
            }
        }
        http.get_response(data)
        return 0
    else:
        log.error("The job order requested send_key, but no public key was provided")
        return -1


def unregister(agent_config, delete_backups=False, debug=False):
    """
    Unregisters this server in TwinDB dispatcher
    Returns
      True    - if server was successfully unregistered
      False   - if error happened
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, log_to_console=True, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)

    data = {
        "type": "unregister",
        "params": {
            "delete_backups": delete_backups,
        }
    }
    log.debug("Unregistration request:")
    log.debug(data)
    response = http.get_response(data)
    if response:
        jd = json.JSONDecoder()
        r = jd.decode(response)
        log.debug(r)
        if r["success"]:
            log.info("The server is successfully unregistered")
            return True
        else:
            gpg = twindb_agent.gpg.TwinDBGPG(agent_config)
            exit_on_error("Failed to unregister the agent: " + jd.decode(gpg.decrypt(r["response"]))["error"])
    else:
        exit_on_error("Empty response from server")
    return False


def take_backup(agent_config, job_order, debug=False):
    """
    Meta function that calls actual backup fucntion depending on tool in backup config
    :param agent_config:
    :param job_order:
    :return: what actual backup function returned or -1 if the tool is not supported
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    log.info("Starting backup job")
    ret = take_backup_xtrabackup(agent_config, job_order, debug)
    log.info("Backup job is complete")
    return ret


def take_backup_xtrabackup(agent_config, job_order, debug=False):
    """
    # Takes backup copy with XtraBackup
    :param agent_config:
    :param job_order: job order
    :return: True if backup was successfully taken or False if it has failed
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
    server_config = get_config(agent_config)
    mysql = twindb_agent.twindb_mysql.MySQL(agent_config,
                                            mysql_user=server_config["mysql_user"],
                                            mysql_password=server_config["mysql_password"],
                                            debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)

    def start_ssh_cmd(file_name, stdin, stderr):
        """
        Starts an SSH process to TwinDB storage and saves input in file backup_name
        :param config: backup config
        :param job_params: job parameters
        :param file_name: file name to save input in
        :param stdin: respective IO handlers
        :param stderr: respective IO handlers
        :return: what SSH process returns
        """
        ssh_process = None
        ssh_cmd = ["ssh", "-oStrictHostKeyChecking=no",
                   "-i", agent_config.ssh_private_key_file,
                   "-p", str(agent_config.ssh_port),
                   "user_id_%s@%s" % (server_config["user_id"], job_order["params"]["ip"]),
                   "/bin/cat - > %s" % file_name]
        try:
            log.debug("Starting SSH process: %r" % ssh_cmd)
            ssh_process = subprocess.Popen(ssh_cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr)
        except OSError as e:
            log.error("Failed to run command %r. %s" % (ssh_cmd, e))
        return ssh_process

    def start_gpg_cmd(stdin, stderr):
        """
        Starts GPG process, encrypts STDIN and outputs in into STDOUT
        :param stdin: respective IO handlers
        :param stderr: respective IO handlers
        :return: what GPG process returns
        """
        gpg_process = None
        gpg_cmd = ["gpg", "--homedir", agent_config.gpg_homedir, "--encrypt", "--yes", "--batch", "--no-permission-warning",
                   "--quiet", "--recipient", agent_config.server_id]
        try:
            log.debug("Starting GPG process: %r" % gpg_cmd)
            gpg_process = subprocess.Popen(gpg_cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr)
        except OSError as e:
            log.error("Failed to run command %r. %s" % (gpg_cmd, e))
        return gpg_process

    def grep_lsn(output):
        """
        Finds LSN in XtraBackup output
        :param output: string with Xtrabackup output
        :return: LSN
        """
        found_lsn = None
        for line in output.split("\n"):
            if line.startswith("xtrabackup: The latest check point (for incremental):"):
                found_lsn = line.split("'")[1]
        return found_lsn

    def record_backup(name, size, backup_lsn=None):
        """
        Saves details about backup copy in TwinDB dispatcher
        :param name: name of backup
        :param vol_id: id of a volume where the backup copy is saved
        :param size: size of the backup in bytes
        :param backup_lsn: last LSN if it was incremental backup
        :param parent: Ansector of the backup (not used now)
        :return: JSON string with status of the request i.e. { "success": True } or None if error happened
        """
        log.info("Saving information about backup:")
        log.info("File name : %s" % name)
        log.info("Volume id : %d" % int(job_order["params"]["volume_id"]))
        log.info("Size      : %d (%s)" % (int(size), twindb_agent.utils.h_size(size)))
        log.info("Ancestor  : %d" % int(job_order["params"]["ancestor"]))
        data = {
            "type": "update_backup_data",
            "params": {
                "job_id": job_order["job_id"],
                "name": name,
                "volume_id": job_order["params"]["volume_id"],
                "size": size,
                "lsn": backup_lsn,
                "ancestor": job_order["params"]["ancestor"]
            }
        }
        log.debug("Saving a record %s" % data)

        response = http.get_response(data)
        if response:
            jd = json.JSONDecoder()
            r = jd.decode(response)
            log.debug(r)
            if r["success"]:
                log.info("Saved backup copy details")
                return True
            else:
                gpg = twindb_agent.gpg.TwinDBGPG(agent_config)
                log.error("Failed to save backup copy details: "
                             + jd.decode(gpg.decrypt(r["response"]))["error"])
                return False
        else:
            log.error("Empty response from server")
            return False

    def gen_extra_config(config):
        """
        Generates MySQL config with datadir option
        :param config: backup config
        :return: File name with MySQL config or None if error happened
        """
        try:
            fd, e_cfg = tempfile.mkstemp()
            os.write(fd, "[mysqld]\n")
            con = mysql.get_mysql_connection()
            cur = con.cursor()
            cur.execute("SELECT @@datadir")
            row = cur.fetchone()
            os.write(fd, 'datadir="%s"\n' % row[0])
            cur.close()
            os.close(fd)
        except IOError as e:
            log.error("Failed to generate extra defaults file. %s" % e)
            e_cfg = None
        return e_cfg

    def get_backup_size(file_name):
        """
        Logs in to TwinDB storage and get size of backup
        :param file_name: file name with backup
        :return: size of backup in bytes or zeor if error happened
        """
        log.debug("Getting size of %s" % backup_name)
        ssh_cmd = ["ssh", "-oStrictHostKeyChecking=no", "-i", agent_config.ssh_private_key_file,
                   "-p", str(agent_config.ssh_port),
                   "user_id_%s@%s" % (server_config["user_id"], job_order["params"]["ip"]), "/bin/du -b %s" % file_name]
        try:
            process = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cout, cerr = process.communicate()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, ' '.join(ssh_cmd), cout)

            cout_lines = cout.split()
            if len(cout_lines) < 1:
                raise subprocess.CalledProcessError(process.returncode, ' '.join(ssh_cmd), cout)

            backup_size = int(cout_lines[0])
        except subprocess.CalledProcessError as e:
            log.error("Failed to get size of backup %s" % backup_name)
            log.error(str(e))
            return 0
        except OSError as e:
            log.error("Failed to get size of backup %s" % backup_name)
            log.error("Failed to run command %r: %s" % (ssh_cmd, e))
            return 0
        log.debug("Size of %s = %d bytes (%s)" % (backup_name, backup_size, twindb_agent.utils.h_size(backup_size)))
        return backup_size

    suffix = "xbstream"
    backup_name = "server_id_%s_%s.%s.gpg" % (agent_config.server_id, datetime.now().isoformat(), suffix)
    ret_code = 0
    if "params" not in job_order:
        log.error("There are no params in the job order")
        return -1
    # Check that job order has all required parameters
    mandatory_params = ["ancestor", "backup_type", "ip", "lsn", "type", "volume_id"]
    for param in mandatory_params:
        if param not in job_order["params"]:
            log.error("There is no %s in the job order" % param)
            return -1
    backup_type = job_order["params"]["backup_type"]
    mysql = twindb_agent.twindb_mysql.MySQL(agent_config, debug=debug)
    server_config = get_config(agent_config)
    xtrabackup_cmd = [
        "innobackupex",
        "--stream=xbstream",
        "--user=%s" % server_config["mysql_user"],
        "--password=%s" % server_config["mysql_password"],
        "--socket=%s" % mysql.get_unix_socket(),
        "--slave-info",
        "--safe-slave-backup",
        "--safe-slave-backup-timeout=3600"]
    if backup_type == 'incremental':
        last_lsn = job_order["params"]["lsn"]
        xtrabackup_cmd.append("--incremental")
        xtrabackup_cmd.append(".")
        xtrabackup_cmd.append("--incremental-lsn=%s" % last_lsn)
    else:
        xtrabackup_cmd.append(".")
    extra_config = gen_extra_config(server_config)
    if extra_config:
        xtrabackup_cmd.append("--defaults-extra-file=%s" % extra_config)
    err_descriptors = dict()
    for desc in ["gpg", "ssh", "xtrabackup"]:
        desc_file = ("/tmp/twindb.%s.err" % desc)
        try:
            err_descriptors[desc] = open(desc_file, "w+")
        except IOError as err:
            log.error("Failed to open file %s. %s" % (desc_file, err))
            return -1
    try:
        log.debug("Starting XtraBackup process: %r" % xtrabackup_cmd)
        xbk_proc = subprocess.Popen(xtrabackup_cmd, stdout=subprocess.PIPE, stderr=err_descriptors["xtrabackup"])
    except OSError as err:
        log.error("Failed to run command %r. %s" % (xtrabackup_cmd, err))
        return -1
    gpg_proc = start_gpg_cmd(xbk_proc.stdout, err_descriptors["gpg"])
    ssh_proc = start_ssh_cmd(backup_name, gpg_proc.stdout, err_descriptors["ssh"])

    xbk_proc.stdout.close()  # Allow p1 to receive a SIGPIPE if p2 exits.
    gpg_proc.stdout.close()  # Allow p2 to receive a SIGPIPE if p3 exits.

    xbk_proc.wait()
    gpg_proc.wait()
    ssh_proc.communicate()

    ret_code_ssh = ssh_proc.returncode
    ret_code_gpg = gpg_proc.returncode
    ret_code_xbk = xbk_proc.returncode

    err_str = dict()
    for desc in ["gpg", "ssh", "xtrabackup"]:
        err_descriptors[desc].seek(0)
        err_str[desc] = err_descriptors[desc].read()
        if not err_str[desc]:
            err_str[desc] = "no output"

    log.info("XtraBackup stderr: " + err_str["xtrabackup"])
    log.info("GPG stderr: " + err_str["gpg"])
    log.info("SSH stderr: " + err_str["ssh"])

    if ret_code_xbk == 0 and ret_code_gpg == 0 and ret_code_ssh == 0:
        lsn = grep_lsn(err_str["xtrabackup"])
        if not lsn:
            log.error("Could not find LSN in XtrabBackup output")
            return -1
        file_size = get_backup_size(backup_name)
        if not file_size:
            log.error("Backup copy size must not be zero")
            return -1
        if not record_backup(backup_name, file_size, lsn):
            log.error("Failed to save backup copy details")
            return -1
    else:
        if ret_code_xbk != 0:
            log.error("XtraBackup exited with code %d" % ret_code_xbk)
        if ret_code_gpg != 0:
            log.error("GPG exited with code %d" % ret_code_gpg)
        if ret_code_ssh != 0:
            log.error("SSH exited with code %d" % ret_code_ssh)
        log.error("Failed to take backup")
        return -1
    for f in [extra_config, "/tmp/twindb.xtrabackup.err", "/tmp/twindb.gpg.err", "/tmp/twindb.ssh.err"]:
        if os.path.isfile(f):
            try:
                os.remove(f)
            except IOError as err:
                log.error("Failed to remove file %s. %s" % (f, err))
    return ret_code


def schedule_backup(agent_config, debug=False):
    """
    Asks dispatcher to schedule a job for this server
    """
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, log_to_console=True, debug=debug)
    http = twindb_agent.httpclient.TwinDBHTTPClient(agent_config, debug=debug)

    data = {
        "type": "schedule_backup",
        "params": {}
    }
    log.debug("Schedule backup request:")
    log.debug(data)
    response = http.get_response(data)
    if response:
        jd = json.JSONDecoder()
        r = jd.decode(response)
        log.debug(r)
        if r["success"]:
            log.info("A backup job is successfully registered")
            return True
        else:
            gpg = twindb_agent.gpg.TwinDBGPG(agent_config)
            log.error("Failed to schedule a job: "
                      + jd.decode(gpg.decrypt(r["response"]))["error"])
            return False
    else:
        exit_on_error("Empty response from server")



