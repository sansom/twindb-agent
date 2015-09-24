import json
import logging
import os
import shutil
import subprocess
import tempfile
import twindb_agent.api
import twindb_agent.config
import twindb_agent.gpg
import twindb_agent.handlers
import twindb_agent.httpclient
import twindb_agent.utils


def execute(job_order, logger_name="twindb_remote"):
    """
    Meta function that calls actual restore fucntion depending on tool in backup config
    :param job_order: job order
    :return: what actual restore function returned or -1 if the tool is not supported
    """
    log = logging.getLogger(logger_name)
    log_params = {"job_id": job_order["job_id"]}
    log.info("Starting restore job: %s"
             % json.dumps(job_order, indent=4, sort_keys=True),
             log_params)
    restore = Restore(job_order)
    ret = restore.restore_xtrabackup()
    log.info("Restore job is complete", log_params)
    return ret


class Restore(object):
    def __init__(self, job_order):
        self.job_order = job_order
        self.logger = logging.getLogger("twindb_remote")
        self.log_params = {"job_id": job_order["job_id"]}

    def error(self, msg):
        self.logger.error(msg, self.log_params)

    def info(self, msg):
        self.logger.info(msg, self.log_params)

    def warning(self, msg):
        self.logger.warning(msg, self.log_params)

    def debug(self, msg):
        self.logger.debug(msg, self.log_params)

    def restore_xtrabackup(self):
        """
        Restores backup copy with XtraBackup
        :return: 0 if backup successfully restored or non-zero if failed
        """
        if "params" not in self.job_order:
            self.error("There are no params in the job order")
            return -1
        # Check that job order has all required parameters
        mandatory_params = ["backup_copy_id", "restore_dir", "server_id"]
        for param in mandatory_params:
            if param not in self.job_order["params"]:
                self.error("There is no %s in the job order" % param)
                return -1
        dst_dir = self.job_order["params"]["restore_dir"]
        try:
            if os.path.isdir(dst_dir):
                if twindb_agent.utils.is_dir_empty(dst_dir):
                    self.info("Directory %s exists. But it's empty, so we can restore backup here" % dst_dir)
                else:
                    self.error("Directory %s exists and isn't empty, so we can not restore backup here" % dst_dir)
                    return -1
            else:
                os.makedirs(dst_dir)
        except IOError as err:
            self.error(err)
            self.error("Can't use directory %s as destination for backup" % dst_dir)
            return -1

        full_copy = True
        backups_chain = self.get_backups_chain()
        if not backups_chain:
            self.error("Failed to get backups chain from dispatcher")
            return -1
        for backup_copy in backups_chain:
            self.debug("Processing backup copy %r" % backup_copy)

            if full_copy:
                if not backup_copy["full"]:
                    self.error("Expected full copy, but it's not")
                    return -1
                if not self.extract_archive(backup_copy, dst_dir):
                    self.error("Failed to extract %s" % backup_copy["name"])
                    return -1
                # We restored full backup copy in dst_dir
                try:
                    xb_err = open('/tmp/twindb.xb.err', "w+")
                except IOError as err:
                    self.error("Failed to open /tmp/twindb.xb.err: %s" % err)
                    return -1
                # if this is the last copy in the chain then --apply-log
                # otherwise just apply the redo log
                if backup_copy["backup_copy_id"] == self.job_order["params"]["backup_copy_id"]:
                    xb_cmd = ["innobackupex", "--apply-log", dst_dir]
                else:
                    xb_cmd = ["innobackupex", "--apply-log", "--redo-only", dst_dir]
                try:
                    p_xb = subprocess.Popen(xb_cmd, stdout=xb_err, stderr=xb_err)
                    p_xb.communicate()
                except OSError as err:
                    self.error("Failed to run %r: %s" % (xb_cmd, err))
                    return -1
                finally:
                    xb_err.seek(0)
                    self.info("innobackupex stderr: " + xb_err.read())
                    os.remove('/tmp/twindb.xb.err')
                if p_xb.returncode != 0:
                    self.error("Failed to apply log on full copy %s" % backup_copy["name"])
                    return -1
                full_copy = False
            else:
                inc_dir = tempfile.mkdtemp()
                if not self.extract_archive(backup_copy, inc_dir):
                    self.error("Failed to extract %s in %s" % (backup_copy["name"], inc_dir))
                try:
                    xb_err = open("/tmp/twindb.xb.err", "w+")
                except IOError as err:
                    self.error("Failed to open /tmp/twindb.xb.err: %s" % err)
                    return -1
                xb_cmd = ["innobackupex", "--apply-log"]
                if backup_copy["backup_copy_id"] != self.job_order["params"]["backup_copy_id"]:
                    xb_cmd.append("--redo-only")
                xb_cmd.append('--incremental-dir=%s' % inc_dir)
                xb_cmd.append(dst_dir)
                try:
                    p_xb = subprocess.Popen(xb_cmd, stdout=xb_err, stderr=xb_err)
                    p_xb.wait()
                except OSError as err:
                    self.error("Failed to run %r: %s" % (xb_cmd, err))
                    return -1
                finally:
                    xb_err.seek(0)
                    self.info("innobackupex stderr: " + xb_err.read())
                    os.remove('/tmp/twindb.xb.err')
                if p_xb.returncode != 0:
                    self.error("Failed to apply log on copy %s" % backup_copy["name"])
                    return -1
                shutil.rmtree(inc_dir)
            self.info("Successfully restored backup %s in %s" % (backup_copy["name"], dst_dir))
        for f in ["/tmp/twindb.xb.err", "/tmp/twindb.gpg.err", "/tmp/twindb.ssh.err"]:
            if os.path.isfile(f):
                os.remove(f)
        return 0

    def extract_archive(self, arc, dst_dir):
        """
        Extracts an Xtrabackup archive arc in  dst_dir
        :param arc: dictionary with archive to extract
        :param dst_dir: local destination directory
        :return:    True - if archive is successfully extracted.
                    False - if error happened
        """
        log = self.logger
        log_params = self.log_params
        server_config = twindb_agent.handlers.get_config()
        agent_config = twindb_agent.config.AgentConfig.get_config()
        mandatory_params = ["backup_copy_id", "name", "ip"]
        for param in mandatory_params:
            if param not in arc:
                log.error("There is no %s in the archive parameters" % param, log_params)
                return False
        log.info("Extracting %s in %s" % (arc["name"], dst_dir), log_params)
        ssh_cmd = [
            "ssh",
            "-oStrictHostKeyChecking=no",
            "-i", agent_config.ssh_private_key_file,
            "-p", str(agent_config.ssh_port),
            "user_id_%s@%s" % (server_config["user_id"], arc["ip"]),
            "/bin/cat %s" % arc["name"]
        ]
        gpg_cmd = ["gpg", "--decrypt"]
        xb_cmd = ["xbstream", "-x"]

        desc_file = None
        try:
            err_desc = dict()
            for desc in ["xb", "gpg", "ssh"]:
                desc_file = ("/tmp/twindb.%s.err" % desc)
                err_desc[desc] = open(desc_file, "w+")
        except IOError as err:
            log.error("Failed to open %s: %s" % (desc_file, err), log_params)
            return False

        log.info("Starting: %r" % ssh_cmd, log_params)
        p1 = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=err_desc["ssh"])
        log.info("Starting: %r" % gpg_cmd, log_params)
        p2 = subprocess.Popen(gpg_cmd, stdin=p1.stdout, stdout=subprocess.PIPE,
                              stderr=err_desc["gpg"])
        log.info("Starting: %r" % xb_cmd, log_params)
        p3 = subprocess.Popen(xb_cmd, stdin=p2.stdout, stdout=subprocess.PIPE,
                              stderr=err_desc["xb"], cwd=dst_dir)
        p1.stdout.close()  # Allow ssh to receive a SIGPIPE if gpg exits.
        p2.stdout.close()  # Allow gpg to receive a SIGPIPE if xtrabackup exits.

        p1.wait()
        p2.wait()
        p3.wait()
        for desc in ["xb", "gpg", "ssh"]:
            err_desc[desc].seek(0)

        log.info("SSH stderr: " + err_desc["ssh"].read(), log_params)
        log.info("GPG stderr: " + err_desc["gpg"].read(), log_params)
        log.info("xbstream stderr: " + err_desc["xb"].read())
        if p1.returncode != 0 or p2.returncode != 0 or p3.returncode != 0:
            log.info("Failed to extract backup %s in %s" % (arc["name"], dst_dir), log_params)
            return False
        desc_file = None
        try:
            for desc in ["xb", "gpg", "ssh"]:
                desc_file = ("/tmp/twindb.%s.err" % desc)
                if os.path.isfile(desc_file):
                    os.remove(desc_file)
        except IOError as err:
            log.error("Failed to open %s: %s" % (desc_file, err), log_params)
        log.info("Extracted successfully %s in %s" % (arc["name"], dst_dir), log_params)
        return True

    def get_backups_chain(self):
        """
        Gets a chain of parents of the given backup_copy_id
        :return: list of dictionaries with backup copy params:
            {
            "backup_copy_id": 188,
            "name": "server_id_479a41b3-d22d-41a8-b7d3-4e40302622f6_2015-04-06T15:10:46.050984.tar.gp",
            "ip": "127.0.0.1",
            full: True
            },
            {...}
        """
        log = self.logger
        log_params = self.log_params
        backup_copy_id = self.job_order["params"]["backup_copy_id"]
        log.debug("Getting backups chain for backup_copy_id %d" % backup_copy_id, log_params)

        data = {
            "type": "get_backups_chain",
            "params": {
                "backup_copy_id": backup_copy_id
            }
        }
        api = twindb_agent.api.TwinDBAPI()
        backups_chain = api.call(data)
        return backups_chain
