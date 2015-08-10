# -*- coding: utf-8 -*-

"""
Classes to work with jobs
"""
import logging
import time
import twindb_agent.config
import twindb_agent.twindb_mysql
import twindb_agent.handlers


class Job(object):
    def __init__(self, job_order):
        self.job_order = job_order
        self.agent_config = twindb_agent.config.AgentConfig.get_config()
        self.logger = logging.getLogger("twindb_remote")
        self.server_config = twindb_agent.handlers.get_config()

    def process(self):
        """
        Processes job
        :return: what respective job function returns or False if error happens
        """
        log = self.logger

        # Check to see that the twindb_agent MySQL user has enough privileges
        username = self.server_config["mysql_user"]
        password = self.server_config["mysql_password"]

        job_id = int(self.job_order["job_id"])
        log_params = {"job_id": job_id}

        try:
            mysql = twindb_agent.twindb_mysql.MySQL()
            mysql_access_available, missing_mysql_privileges = mysql.has_mysql_access(grant_capability=False)
            if not mysql_access_available:
                log.error("The MySQL user %s does not have all the required privileges." % username, log_params)
                if missing_mysql_privileges:
                    raise JobError("You can grant the required privileges by executing the following SQL: "
                                   "GRANT %s ON *.* TO '%s'@'localhost' IDENTIFIED BY '%s'; FLUSH PRIVILEGES;"
                                   % (','.join(missing_mysql_privileges), username, password))
            if not self.job_order["start_scheduled"]:
                raise JobError("Job start time isn't set")

            if not twindb_agent.handlers.log_job_notify(params={"event": "start_job",
                                                                "job_id": job_id}):
                raise JobError("Failed to notify dispatcher about job start")

            log.info("Processing job_id = %d" % job_id, log_params)
            start_scheduled = int(self.job_order["start_scheduled"])
            now = int(time.time())
            delay = start_scheduled - now
            if delay < 0:
                delay = 0
            log.info("Wating %d seconds before job is started" % delay, log_params)
            time.sleep(delay)

            if self.job_order["type"] == "backup":
                ret = self.take_backup()
            elif self.job_order["type"] == "restore":
                ret = self.restore_backup()
            elif self.job_order["type"] == "send_key":
                ret = self.send_key()
            else:
                raise JobError("Unsupported job type " + self.job_order["type"])

            log.info("job_id = %d finished with code %d" % (job_id, ret), log_params)

            twindb_agent.handlers.log_job_notify(params={"event": "stop_job",
                                                         "job_id": job_id,
                                                         "ret_code": ret})
        except JobError as err:
            log.error("Job error: %s", err, log_params)

            twindb_agent.handlers.log_job_notify(params={"event": "stop_job",
                                                         "job_id": job_id,
                                                         "ret_code": -1})
            return False
        except JobTooSoonError as err:
            log.debug(err, log_params)
            return False
        return True

    def send_key(self):
        return twindb_agent.handlers.send_key(job_order=self.job_order)

    def take_backup(self):
        return twindb_agent.handlers.take_backup(self.job_order)

    def restore_backup(self):
        if self:
            pass
        return 0


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
