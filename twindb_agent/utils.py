"""
Auxilary functions
"""
import os
import traceback

import twindb.loggin_local
import errno
import time
import twindb.globals
import sys

log = twindb.loggin_local.getlogger(__name__)


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
        exit_on_error("TwinDB agent must be run by root")
    log.debug("Environment is OK")
    return True


def is_dir_empty(directory):
    """
    Checks if directory is empty
    :param directory: directory name
    :return: True if the directory is empty of False otherwise
    """
    return len(os.listdir(directory)) == 0


def pid_exists(pid):
    """
    Checks whether pid exists in the current process table.
    """
    if pid < 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as e:
        return e.errno == errno.EPERM
    else:
        return True


class TimeoutExpired(Exception):
    pass


def wait_pid(pid, timeout=None):
    """Wait for process with pid 'pid' to terminate and return its
    exit status code as an integer.

    If pid is not a children of os.getpid() (current process) just
    waits until the process disappears and return None.

    If pid does not exist at all return None immediately.

    Raise TimeoutExpired on timeout expired (if specified).
    """

    def check_timeout(timeout_delay):
        if timeout is not None:
            if time.time() >= stop_at:
                raise TimeoutExpired
        time.sleep(timeout_delay)
        return min(timeout_delay * 2, 0.04)

    if timeout is not None:
        waitcall = lambda: os.waitpid(pid, os.WNOHANG)
        stop_at = time.time() + timeout
    else:
        waitcall = lambda: os.waitpid(pid, 0)

    delay = 0.0001
    while 1:
        try:
            retpid, status = waitcall()
        except OSError, err:
            if err.errno == errno.EINTR:
                delay = check_timeout(delay)
                continue
            elif err.errno == errno.ECHILD:
                # This has two meanings:
                # - pid is not a child of os.getpid() in which case
                #   we keep polling until it's gone
                # - pid never existed in the first place
                # In both cases we'll eventually return None as we
                # can't determine its exit status code.
                while 1:
                    if pid_exists(pid):
                        delay = check_timeout(delay)
                    else:
                        return
            else:
                raise
        else:
            if retpid == 0:
                # WNOHANG was used, pid is still running
                delay = check_timeout(delay)
                continue
            # process exited due to a signal; return the integer of
            # that signal
            if os.WIFSIGNALED(status):
                return os.WTERMSIG(status)
            # process exited using exit(2) system call; return the
            # integer exit(2) system call has been called with
            elif os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
            else:
                # should never happen
                raise RuntimeError("unknown process exit status")


def remove_pid():
    """
    Removes pid file
    :return: nothing
    Exits if error happened
    """
    if os.path.isfile(twindb.globals.pid_file):
        try:
            os.remove(twindb.globals.pid_file)
        except IOError as err:
            exit_on_error("Failed to remove file %s. %s" % (twindb.globals.pid_file, err))


def check_pid():
    """
    Checks if pid file already exists.
    If it does it detects whether twindb agent is already running.
    If the pid file is stale it removes it.
    :return: True if pid file doesn't exist or was stale and it was removed.
    False if twindb agent is running or error happened
    """
    if os.path.isfile(twindb.globals.pid_file):
        pid = read_pid()
        if pid_exists(pid):
            try:
                f = open("/proc/%d/cmdline" % pid, "r")
                cmdline = f.readline()
                f.close()
                if "twindb" in cmdline:
                    # The process is a live twindb agent
                    return False
                else:
                    # It's some other process, not a twindb agent
                    remove_pid()
            except IOError as err:
                log.error(err)
                remove_pid()
        else:
            remove_pid()

    # pid file doesn't exist
    return True


def read_pid():
    """
    Read pid from pid_file
    :return: pid or zero if pid file doesn't exist
    """
    try:
        f = open(twindb.globals.pid_file, 'r')
        pid = int(f.readline())
        f.close()
    except IOError as err:
        log.error("Couldn't read from %s: %s" % (twindb.globals.pid_file, err))
        return 0
    return int(pid)


def write_pid():
    """
    Writes pid of the current process to the pid file
    :return: nothing.
    Exists if error happened
    """
    try:
        f = open(twindb.globals.pid_file, "w")
        f.write(str(os.getpid()))
        f.close()
    except IOError as err:
        log.error("Couldn't save process id in " + twindb.globals.pid_file)
        exit_on_error(err)


def cleanup(signum, frame):
    """
    Cleans up when TwinDB agent exists
    :param signum:
    :param frame:
    :return:
    """

    log.info("Cleaning up on signal " + str(signum))
    log.debug("Frame %r" % frame)
    log.info("TwinDB agent is ready to exit")
    sys.exit(0)


def exit_on_error(message):
    """
    Reports error removes pid and exits
    :rtype : object
    :param message: message to display
    :return:
    """
    log.error(message)
    log.debug(traceback.format_exc())
    sys.exit(2)