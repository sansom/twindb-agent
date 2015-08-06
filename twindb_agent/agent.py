# -*- coding: utf-8 -*-
import json

import multiprocessing
import time
import sys

import twindb_agent.job
import twindb_agent.logging_remote
import twindb_agent.gpg
import twindb_agent.handlers


class Agent(object):
    def __init__(self, config, debug=False):
        self.config = config
        self.debug = debug
        self.logger = twindb_agent.logging_remote.getlogger(__name__, config, debug)
        self.gpg = twindb_agent.gpg.TwinDBGPG(config, debug=debug)
        self.logger.debug("Agent initialized")
        pass

    def start(self):
        log = self.logger
        log.info("Agent is starting")
        while True:
            if self.is_registered():
                log.error("Checking if there are any new job orders")
                job_order = self.get_job_order()
                if job_order:
                    log.info("Received job order %s" % json.dumps(job_order, indent=4, sort_keys=True))
                    job = twindb_agent.job.Job(job_order, self.config, debug=self.debug)
                    proc = multiprocessing.Process(target=job.process,
                                                   name="%s-%s" % (job_order["type"], job_order["job_id"]))
                    log.error("before run")
                    proc.start()
                    log.error("after run")

                # Report replication status
                log.error("Reporting replication status")
                proc = multiprocessing.Process(target=twindb_agent.handlers.report_sss,
                                               name="report_sss",
                                               args=(self.config, self.debug))
                proc.start()

                # Report agent privileges
                log.error("Reporting agent granted privileges")
                proc = multiprocessing.Process(target=twindb_agent.handlers.report_agent_privileges,
                                               name="report_agent_privileges",
                                               args=(self.config, self.debug))
                proc.start()

                # Calling this has the side affect of “joining” any processes which have already finished.
                multiprocessing.active_children()
            else:
                log.warn("This agent(%s) isn't registered" % self.config.server_id)
            time.sleep(self.config.check_period)

    def stop(self):
        log = self.logger
        for proc in multiprocessing.active_children():
            log.info("Terminating process %s" % proc.name)
            proc.terminate()
        sys.exit(0)

    def register(self, reg_code):
        if twindb_agent.handlers.register(reg_code, agent_config=self.config, debug=self.debug):
            twindb_agent.handlers.commit_registration(agent_config=self.config, debug=self.debug)

    def unregister(self, delete_backups=False):
        twindb_agent.handlers.unregister(self.config, delete_backups=delete_backups, debug=self.debug)

    def is_registered(self):
        return twindb_agent.handlers.is_registered(self.config, self.debug)

    def get_job_order(self):
        return twindb_agent.handlers.get_job(self.config, self.debug)

    def backup(self):
        log = self.logger
        if twindb_agent.handlers.schedule_backup(self.config, debug=self.debug):
            job_order = self.get_job_order()
            log.info("Received job order %s" % json.dumps(job_order, indent=4, sort_keys=True))
            job = twindb_agent.job.Job(job_order, self.config, debug=self.debug)
            job.process()
