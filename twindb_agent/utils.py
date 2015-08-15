"""
Auxilary functions
"""
import logging
import os
import sys

log = logging.getLogger("twindb_local")


def h_size(num, decimals=2):
    """
    Formats bytes count to human readable form
    Inputs:
      num         - bytes count
      decimals    - number of digits to save after point (Default 2)
    Returns
      human-readable string like "20.33 MB"
    """
    fmt = "%3." + str(decimals) + "f %s"
    for x in ['bytes', 'kB', 'MB', 'GB', 'TB', 'PB']:
        if num < 1024.0:
            return fmt % (num, x)
        num /= 1024.0


def sanitize_config(config):
    """
    Replaces password from config with ********
    :param config: python dictionary with backup config
    :return: Sanitized config
    """

    if not config:
        return None
    sanitized_config = dict(config)
    if "mysql_password" in config:
        sanitized_config["mysql_password"] = "********"
    else:
        log.debug("Given config %r doesn't contain password" % config)
    return sanitized_config


def check_env():
    """
    Checks the environment if it's OK to start TwinDB agent
    Returns
      True    - if the environment is OK
    Exits if the environment is not OK
    """
    log.debug("Checking environment")
    if os.getuid() != 0:
        log.error("TwinDB agent must be run by root")
        sys.exit(2)
    log.debug("Environment is OK")
    return True


def is_dir_empty(directory):
    """
    Checks if directory is empty
    :param directory: directory name
    :return: True if the directory is empty of False otherwise
    """
    return len(os.listdir(directory)) == 0
