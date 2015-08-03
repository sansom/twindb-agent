"""
TwinDB class for local and remote logging
"""
import logging

import twindb.logging_local
import twindb.httpclient


class RlogHandler(logging.Handler):
    """
    Logging handler that logs to remote TwiDB dispatcher
    """
    def __init__(self, server_id):
        logging.Handler.__init__(self)
        self.server_id = server_id

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
        httpclient = twindb.httpclient.TwinDBHTTPClient(self.server_id)
        httpclient.get_response(request)


def getlogger(name, server_id, debug=False):
    logger = twindb.logging_local.getlogger(name, debug)
    remote_handler = RlogHandler(server_id)
    remote_handler.setFormatter("%(name)s: %(levelname)s: %(funcName)s():%(lineno)d: %(message)s")
    logger.addHandler(remote_handler)
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger