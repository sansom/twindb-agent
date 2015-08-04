# -*- coding: utf-8 -*-

"""
Base class for local logging
"""

import logging
import logging.handlers
import os


class TwinDBLoggingException(Exception):
    pass


def getlogger(name, debug=False):
    logger = logging.getLogger(name)
    if not logger.handlers:
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

        fmt_str = "%(asctime)s: %(name)s: %(levelname)s: %(funcName)s():%(lineno)d: %(message)s"
        file_handler.setFormatter(logging.Formatter(fmt_str))

        logger.addHandler(file_handler)
        logger.setLevel(logging.INFO)
        if debug:
            logger.setLevel(logging.DEBUG)

    return logger
