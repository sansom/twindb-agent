import tempfile
import datetime
import fcntl
import twindb_agent.api
import twindb_agent.config
import twindb_agent.gpg
import twindb_agent.httpclient
import twindb_agent.twindb_mysql
import twindb_agent.utils

from twindb_agent.handlers import *


def execute(job_order, logger_name="twindb_remote"):
    """
    Meta function that calls actual backup fucntion depending on tool in backup config
    :param job_order:
    :return: what actual backup function returned or -1 if the tool is not supported
    """
    log = logging.getLogger(logger_name)
    log_params = {"job_id": job_order["job_id"]}
    log.info("Starting backup job", log_params)
    ret = take_backup_xtrabackup(job_order, logger_name)
    log.info("Backup job is complete", log_params)
    return ret


def take_backup_xtrabackup(job_order, logger_name):
    """
    # Takes backup copy with XtraBackup
    :param job_order: job order
    :return: True if backup was successfully taken or False if it has failed
    """
    agent_config = twindb_agent.config.AgentConfig.get_config()
    log = logging.getLogger(logger_name)
    log_params = {"job_id": job_order["job_id"]}
    server_config = get_config()
    mysql = twindb_agent.twindb_mysql.MySQL(mysql_user=server_config["mysql_user"],
                                            mysql_password=server_config["mysql_password"])

    def start_ssh_cmd(file_name, stdin, stderr):
        """
        Starts an SSH process to TwinDB storage and saves input in file backup_name
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
            log.debug("Starting SSH process: %r" % ssh_cmd, log_params)
            ssh_process = subprocess.Popen(ssh_cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr)
        except OSError as e:
            log.error("Failed to run command %r. %s" % (ssh_cmd, e), log_params)
        return ssh_process

    def start_gpg_cmd(stdin, stderr):
        """
        Starts GPG process, encrypts STDIN and outputs in into STDOUT
        :param stdin: respective IO handlers
        :param stderr: respective IO handlers
        :return: what GPG process returns
        """
        gpg_process = None
        gpg_cmd = ["gpg", "--homedir", agent_config.gpg_homedir, "--encrypt", "--yes", "--batch",
                   "--no-permission-warning",
                   "--quiet", "--recipient", agent_config.server_id]
        try:
            log.debug("Starting GPG process: %r" % gpg_cmd, log_params)
            gpg_process = subprocess.Popen(gpg_cmd, stdin=stdin, stdout=subprocess.PIPE, stderr=stderr)
        except OSError as e:
            log.error("Failed to run command %r. %s" % (gpg_cmd, e), log_params)
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
        :param size: size of the backup in bytes
        :param backup_lsn: last LSN if it was incremental backup
        :return: JSON string with status of the request i.e. { "success": True } or None if error happened
        """
        log.info("Saving information about backup:", log_params)
        log.info("File name : %s" % name, log_params)
        log.info("Volume id : %d" % int(job_order["params"]["volume_id"]), log_params)
        log.info("Size      : %d (%s)" % (int(size), twindb_agent.utils.h_size(size)), log_params)
        log.info("Ancestor  : %d" % int(job_order["params"]["ancestor"]), log_params)
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
        log.debug("Saving a record %s" % data, log_params)
        api = twindb_agent.api.TwinDBAPI(logger_name=logger_name)
        api.call(data)
        if api.success:
            log.info("Saved backup copy details", log_params)
            return True
        else:
            log.error("Failed to save backup copy details")
            return False

    def gen_extra_config():
        """
        Generates MySQL config with datadir option
        :return: File name with MySQL config or None if error happened
        """
        try:
            fd, e_cfg = tempfile.mkstemp()
            os.write(fd, "[mysqld]\n")
            con = mysql.get_mysql_connection()
            if con:
                cur = con.cursor()
                cur.execute("SELECT @@datadir")
                row = cur.fetchone()
                os.write(fd, 'datadir="%s"\n' % row[0])
                cur.close()
                os.close(fd)
            else:
                return None
        except IOError as e:
            log.error("Failed to generate extra defaults file. %s" % e, log_params)
            e_cfg = None
        return e_cfg

    def get_backup_size(file_name):
        """
        Logs in to TwinDB storage and get size of backup
        :param file_name: file name with backup
        :return: size of backup in bytes or zeor if error happened
        """
        log.debug("Getting size of %s" % backup_name, log_params)
        ssh_cmd = ["ssh", "-oStrictHostKeyChecking=no", "-i", agent_config.ssh_private_key_file,
                   "-p", str(agent_config.ssh_port),
                   "user_id_%s@%s" % (server_config["user_id"], job_order["params"]["ip"]), "/bin/du -b %s" % file_name]
        try:
            process = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            cout, cerr = process.communicate()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, "%s: %s" % (' '.join(ssh_cmd), cout))

            cout_lines = cout.split()
            if len(cout_lines) < 1:
                raise subprocess.CalledProcessError(process.returncode, "%s: %s" % (' '.join(ssh_cmd), cout))

            backup_size = int(cout_lines[0])
        except subprocess.CalledProcessError as e:
            log.error("Failed to get size of backup %s" % backup_name, log_params)
            log.error(str(e))
            return 0
        except OSError as e:
            log.error("Failed to get size of backup %s" % backup_name, log_params)
            log.error("Failed to run command %r: %s" % (ssh_cmd, e), log_params)
            return 0
        log.debug("Size of %s = %d bytes (%s)" % (backup_name, backup_size, twindb_agent.utils.h_size(backup_size)),
                  log_params)
        return backup_size

    suffix = "xbstream"
    backup_name = "server_id_%s_%s.%s.gpg" % (agent_config.server_id, datetime.datetime.now().isoformat(), suffix)
    ret_code = 0
    if "params" not in job_order:
        log.error("There are no params in the job order", log_params)
        return -1
    # Check that job order has all required parameters
    mandatory_params = ["ancestor", "backup_type", "ip", "lsn", "type", "volume_id"]
    for param in mandatory_params:
        if param not in job_order["params"]:
            log.error("There is no %s in the job order" % param, log_params)
            return -1
    backup_type = job_order["params"]["backup_type"]
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
    extra_config = gen_extra_config()
    if extra_config:
        xtrabackup_cmd.append("--defaults-extra-file=%s" % extra_config)
    err_descriptors = dict()
    for desc in ["gpg", "ssh", "xtrabackup"]:
        desc_file = ("/tmp/twindb.%s.err" % desc)
        try:
            err_descriptors[desc] = open(desc_file, "w+")
        except IOError as err:
            log.error("Failed to open file %s. %s" % (desc_file, err), log_params)
            return -1
    # Grab an exclusive lock to make sure only one XtrBackup process is runnning
    lockfile = open("/tmp/twindb.xtrabackup.lock", "w+")
    fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
    try:
        log.debug("Starting XtraBackup process: %r" % xtrabackup_cmd, log_params)
        xbk_proc = subprocess.Popen(xtrabackup_cmd, stdout=subprocess.PIPE, stderr=err_descriptors["xtrabackup"])
    except OSError as err:
        log.error("Failed to run command %r. %s" % (xtrabackup_cmd, err), log_params)
        return -1
    gpg_proc = start_gpg_cmd(xbk_proc.stdout, err_descriptors["gpg"])
    ssh_proc = start_ssh_cmd(backup_name, gpg_proc.stdout, err_descriptors["ssh"])

    xbk_proc.stdout.close()  # Allow xbk_proc to receive a SIGPIPE if gpg exits.
    gpg_proc.stdout.close()  # Allow gpg_proc to receive a SIGPIPE if ssh exits.

    xbk_proc.wait()
    gpg_proc.wait()
    ssh_proc.communicate()

    ret_code_ssh = ssh_proc.returncode
    ret_code_gpg = gpg_proc.returncode
    ret_code_xbk = xbk_proc.returncode

    err_str = dict()
    for desc in ["gpg", "ssh", "xtrabackup"]:
        try:
            err_descriptors[desc].seek(0)
            err_str[desc] = err_descriptors[desc].read()
            if not err_str[desc]:
                err_str[desc] = "no output"
        except IOError as err:
            err_str[desc] = "Failed to read output"
            log.error(err)

    log.info("XtraBackup stderr: " + err_str["xtrabackup"])
    log.info("GPG stderr: " + err_str["gpg"])
    log.info("SSH stderr: " + err_str["ssh"])

    if ret_code_xbk == 0 and ret_code_gpg == 0 and ret_code_ssh == 0:
        lsn = grep_lsn(err_str["xtrabackup"])
        if not lsn:
            log.error("Could not find LSN in XtrabBackup output", log_params)
            return -1
        file_size = get_backup_size(backup_name)
        if not file_size:
            log.error("Backup copy size must not be zero", log_params)
            return -1
        if not record_backup(backup_name, file_size, lsn):
            log.error("Failed to save backup copy details", log_params)
            return -1
    else:
        if ret_code_xbk != 0:
            log.error("XtraBackup exited with code %d" % ret_code_xbk, log_params)
        if ret_code_gpg != 0:
            log.error("GPG exited with code %d" % ret_code_gpg, log_params)
        if ret_code_ssh != 0:
            log.error("SSH exited with code %d" % ret_code_ssh, log_params)
        log.error("Failed to take backup", log_params)
        return -1

    for desc in ["gpg", "ssh", "xtrabackup"]:
        err_descriptors[desc].close()

    for f in [extra_config, "/tmp/twindb.xtrabackup.err", "/tmp/twindb.gpg.err", "/tmp/twindb.ssh.err"]:
        if os.path.isfile(f):
            try:
                os.remove(f)
            except IOError as err:
                log.error("Failed to remove file %s. %s" % (f, err), log_params)
    return ret_code
