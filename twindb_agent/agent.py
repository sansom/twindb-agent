import json
import logging
import multiprocessing
import time
import sys
import fcntl

import twindb_agent.config
import twindb_agent.gpg
import twindb_agent.handlers
import twindb_agent.job
import twindb_agent.utils


class Agent(object):
    def __init__(self):
        self.config = twindb_agent.config.AgentConfig.get_config()
        self.logger = logging.getLogger("twindb_remote")
        self.gpg = twindb_agent.gpg.TwinDBGPG()
        self.logger.debug("Agent initialized")
        pass

    def start(self):
        log = self.logger
        log.info("Agent is starting")
        while True:
            if self.is_registered():
                log.debug("Checking if there are any new job orders")
                job_order = self.get_job_order()
                if job_order:
                    log.info("Received job order %s" % json.dumps(job_order, indent=4, sort_keys=True))
                    job = twindb_agent.job.Job(job_order)
                    proc = multiprocessing.Process(target=job.process,
                                                   name="%s-%s" % (job_order["type"], job_order["job_id"]))
                    proc.start()
                    # Dispatcher can't handle parallel jobs. Will wait till job finishes.
                    # After the bug is fixed .join() should be removed
                    # https://bugs.launchpad.net/twindb/+bug/1484342
                    proc.join()

                # Report replication status
                log.debug("Reporting replication status")
                proc = multiprocessing.Process(target=twindb_agent.handlers.report_show_slave_status,
                                               name="report_sss")
                proc.start()

                # Report agent privileges
                log.debug("Reporting agent granted privileges")
                proc = multiprocessing.Process(target=twindb_agent.handlers.report_agent_privileges,
                                               name="report_agent_privileges")
                proc.start()

                # Calling this has the side affect of "joining" any processes which have already finished.
                multiprocessing.active_children()
            else:
                log.warn("This agent(%s) isn't registered" % self.config.server_id)
            time.sleep(self.config.check_period)

    @staticmethod
    def stop(signum=None, frame=None):
        log = logging.getLogger("twindb_remote")
        if signum:
            log.info("TwinDB agent process received signal %d" % signum)
        # log.info("Shutting down TwinDB agent")
        # shut up pycharm warning
        if frame:
            pass

        for proc in multiprocessing.active_children():
            log.info("Terminating process %s" % proc.name)
            proc.terminate()
            proc.join()
        # log.info("TwinDB agent successfully shut down")

        sys.exit(0)

    @staticmethod
    def register(reg_code):
        log = logging.getLogger("twindb_console")
        if twindb_agent.handlers.register(reg_code):
            # TODO Implement commit_registration handler in dispatcher
            # if not twindb_agent.handlers.commit_registration():
            #     log.error("Failed to confirm agent registartion")
            #     sys.exit(2)
            log.info("Agent is successfully registered")
            pass
        else:
            log.error("Agent registration failed")
            sys.exit(2)

    @staticmethod
    def unregister(delete_backups=False):
        twindb_agent.handlers.unregister(delete_backups=delete_backups)

    @staticmethod
    def is_registered():
        return twindb_agent.handlers.is_registered()

    @staticmethod
    def get_job_order():
        return twindb_agent.handlers.get_job()

    def backup(self):
        log = logging.getLogger("twindb_console")
        if twindb_agent.handlers.schedule_backup():
            job_order = self.get_job_order()
            if job_order:
                log.info("Received job order %s" % json.dumps(job_order, indent=4, sort_keys=True))
                if job_order["type"] != "backup":
                    log.warning("We scheduled backup job, but the dispatcher sent '%s' job order." % job_order["type"])
                    log.warning("TwinDB agent will eventually execute the backup job if it's running")
                    sys.exit(0)
                try:
                    lockfile = open("/tmp/twindb.xtrabackup.lock", "w+")
                    fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    log.warning("The local agent is already executing a backup job")
                    log.warning("The backup will be taken by the running agent when the current backup job is done")
                    sys.exit(2)

                job = twindb_agent.job.Job(job_order)
                log.info("Starting backup job")
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
                if job.process():
                    log.info("Backup is successfully completed")
                else:
                    log.error("Failed to take backup")
            else:
                log.error("Didn't receive job order although backup job was successfully scheduled")
        else:
            log.error("Failed to schedule a backup job")
            sys.exit(2)
