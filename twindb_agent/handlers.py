# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
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
    log = twindb_agent.logging_remote.getlogger(__name__, agent_config, debug=debug)
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

