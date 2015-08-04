# -*- coding: utf-8 -*-

"""
TwinDB class for local and remote logging
"""
import logging

import twindb_agent.logging_local
import twindb_agent.httpclient


class RlogHandler(logging.Handler):
    """
    Logging handler that logs to remote TwiDB dispatcher
    """
    def __init__(self, agent_config):
        logging.Handler.__init__(self)
        self.agent_config = agent_config

    def emit(self, record):
        request = {
            "type": "log",
            "params": {}
        }

        try:
            job_id = record.args["job_id"]
            request["params"]["job_id"] = job_id
        except TypeError:
            # if job_id isn't passed TypeError will be raisen
            pass
        except KeyError:
            # If there is no job_id key in args KeyError will be raisen
            pass
        request["params"]["msg"] = record.getMessage()
        httpclient = twindb_agent.httpclient.TwinDBHTTPClient(self.agent_config, debug=False)
        httpclient.get_response(request)


def getlogger(name, server_id, log_to_console=False, debug=False):
    logger = twindb_agent.logging_local.getlogger(name, log_to_console=log_to_console, debug=debug)

    remote_handler_added = False
    for lh in logger.handlers:
        if isinstance(lh, RlogHandler):
            remote_handler_added = True

    if not remote_handler_added:
        remote_handler = RlogHandler(server_id)
        remote_handler.setFormatter("%(name)s: %(levelname)s: %(funcName)s():%(lineno)d: %(message)s")
        if remote_handler not in logger.handlers:
            logger.addHandler(remote_handler)
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger
