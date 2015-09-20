import logging
import logging.handlers
import os
import twindb_agent.config
import twindb_agent.httpclient

FMT_STR = "%(asctime)s: %(processName)s: %(levelname)s: %(module)s: %(funcName)s():%(lineno)d: %(message)s"
FMT_REMOTE_STR = "%(levelname)s: %(processName)s: %(module)s: %(funcName)s():%(lineno)d: %(message)s"


class RlogHandler(logging.Handler):
    """
    Logging handler that logs to remote TwiDB dispatcher
    """
    def __init__(self):
        logging.Handler.__init__(self)

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
        httpclient = twindb_agent.httpclient.TwinDBHTTPClient()
        httpclient.get_response(request)


def create_local_logger(debug=False):
    logger = logging.getLogger("twindb_local")
    log_dir = "/var/log/twindb"
    try:
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
    except OSError as err:
        raise TwinDBLoggingException("Failed to create directory %s: %s" % (log_dir, err))

    log_file = "%s/twindb-agent.log" % log_dir
    try:
        file_handler = logging.handlers.WatchedFileHandler(log_file)
    except IOError as err:
        raise TwinDBLoggingException("Faield to open %s: %s" % (log_file, err))

    file_handler.setFormatter(logging.Formatter(FMT_STR))
    logger.addHandler(file_handler)

    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    return logger


def create_remote_logger(debug=False, debug_local=False):
    logger = logging.getLogger("twindb_remote")

    log_dir = "/var/log/twindb"
    try:
        if not os.path.exists(log_dir):
            os.mkdir(log_dir)
    except OSError as err:
        raise TwinDBLoggingException("Failed to create directory %s: %s" % (log_dir, err))

    log_file = "%s/twindb-agent.log" % log_dir
    try:
        file_handler = logging.handlers.WatchedFileHandler(log_file)
    except IOError as err:
        raise TwinDBLoggingException("Faield to open %s: %s" % (log_file, err))

    file_handler.setFormatter(logging.Formatter(FMT_STR))
    logger.addHandler(file_handler)

    if not debug_local:
        remote_handler = RlogHandler()
        remote_handler.setFormatter(FMT_REMOTE_STR)
        logger.addHandler(remote_handler)

    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    return logger


def create_console_logger(debug=False):
    logger = logging.getLogger("twindb_console")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(FMT_STR))
    logger.addHandler(console_handler)

    logger.addHandler(console_handler)

    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    return logger


class TwinDBLoggingException(Exception):
    pass
