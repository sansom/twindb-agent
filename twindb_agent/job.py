"""
Classes to work with jobs
"""
import json
import logging
import os
import time
import twindb_agent.config
import twindb_agent.twindb_mysql
import twindb_agent.handlers


class Job(object):
    def __init__(self, job_order, logger_name="twindb_remote"):
        # TODO "params" in a job order is a string on some reason.
        # Until it's fixed decode params
        # https://bugs.launchpad.net/twindb/+bug/1485032
        job_params = json.JSONDecoder().decode(job_order["params"])
        job_order["params"] = job_params
        self.job_order = job_order
        self.agent_config = twindb_agent.config.AgentConfig.get_config()
        self.logger_name = logger_name
        self.logger = logging.getLogger(logger_name)
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
        log.info("Processing job_id = %d" % job_id, log_params)

        try:
            mysql = twindb_agent.twindb_mysql.MySQL(mysql_user=username, mysql_password=password)
            mysql_access_available, missing_mysql_privileges = mysql.has_mysql_access(grant_capability=False)
            if not mysql_access_available:
                log.error("The MySQL user %s does not have all the required privileges." % username, log_params)
                if missing_mysql_privileges:
                    raise JobError("You can grant the required privileges by executing the following SQL: "
                                   "GRANT %s ON *.* TO '%s'@'localhost' IDENTIFIED BY '%s'; FLUSH PRIVILEGES;"
                                   % (','.join(missing_mysql_privileges), username, password))
            if not self.job_order["start_scheduled"]:
                raise JobError("Job start time isn't set")

            start_scheduled = int(self.job_order["start_scheduled"])
            now = int(time.time())
            delay = start_scheduled - now
            if delay < 0:
                delay = 0
            log.info("Wating %d seconds before job is started" % delay, log_params)
            time.sleep(delay)

            if not twindb_agent.handlers.log_job_notify(params={"event": "start_job",
                                                                "job_id": job_id,
                                                                "pid": os.getpid()}):
                raise JobError("Failed to notify dispatcher about job start")

            # Execute a job
            module_name = "twindb_agent.job_type.%s" % self.job_order["type"]
            module = __import__(module_name, globals(), locals(), [self.job_order["type"]])
            ret = module.execute(self.job_order, self.logger_name)

            log.info("job_id = %d finished with code %d" % (job_id, ret), log_params)

            twindb_agent.handlers.log_job_notify(params={"event": "stop_job",
                                                         "job_id": job_id,
                                                         "ret_code": ret})
        except JobError as err:
            log.error("Job error: %s" % err, log_params)

            twindb_agent.handlers.log_job_notify(params={"event": "stop_job",
                                                         "job_id": job_id,
                                                         "ret_code": -1})
            return False
        except JobTooSoonError as err:
            log.debug(err, log_params)
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
