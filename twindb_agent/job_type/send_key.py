import logging
import subprocess

import twindb_agent.api
import twindb_agent.config
import twindb_agent.httpclient


def execute(job_order):
    """
    Processes send_key job
    :return: nothing
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger("twindb_remote")

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
        api = twindb_agent.api.TwinDBAPI()
        api.call(data)
        if api.success:
            return 0
        else:
            return -1
    else:
        log.error("The job order requested send_key, but no public key was provided")
        return -1
