"""
Classes to work with jobs
"""
import time
import twindb


class Job(object):
    def __init__(self, server_id, config, job, debug=False):
        self.config = config
        self.job = job
        self.server_id = server_id
        self.logger = twindb.logging_remote.getlogger(__name__, server_id, debug=debug)

    def process(self):
        """
        Processes job
        :return: what respective job function returns or False if error happens
        """
        log = self.logger

        # Check to see that the twindb_agent MySQL user has enough privileges
        username = self.config["mysql_user"]
        password = self.config["mysql_password"]

        job_id = int(self.job["job_id"])

        try:
            mysql = twindb.mysql.MySQL(self.server_id, username, password)
            mysql_access_available, missing_mysql_privileges = mysql.has_mysql_access(username, password,
                                                                                      grant_capability=False)
            if not mysql_access_available:
                log.error("The MySQL user %s does not have all the required privileges." % username)
                if missing_mysql_privileges:
                    raise JobError("You can grant the required privileges by executing the following SQL: "
                                   "GRANT %s ON *.* TO '%s'@'localhost' IDENTIFIED BY '%s'; FLUSH PRIVILEGES;"
                                   % (','.join(missing_mysql_privileges), username, password))
            if not self.job["start_scheduled"]:
                raise JobError("Job start time isn't set")
            start_scheduled = int(self.job["start_scheduled"])
            now = int(time.time())
            if now < start_scheduled:
                raise JobTooSoonError("Job is scheduled on %s, now %s"
                                      % (time.ctime(start_scheduled), time.ctime(now)))
            log.info("Processing job_id = %d", int(job_id))
            notify_params = {"event": "start_job", "job_id": int(job_id)}
            if not log_job_notify(notify_params):
                raise JobError("Failed to notify dispatcher abot job start")
            if job["type"] == "backup":
                ret = take_backup(config, job)
            elif job["type"] == "restore":
                ret = restore_backup(config, job)
            elif job["type"] == "send_key":
                ret = handler_send_key(job)
            else:
                raise JobError("Unsupported job type " + job["type"])
            notify_params = {"event": "stop_job", "job_id": job["job_id"], "ret_code": ret}
            log_job_notify(notify_params)
        except JobError as err:
            log.error("Job error: %s", err)
            notify_params = {"event": "stop_job", "job_id": job["job_id"], "ret_code": -1}
            log_job_notify(notify_params)
            return False
        except JobTooSoonError as err:
            log.debug(err)
            return False
        return True


class JobError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value


class JobTooSoonError(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value
