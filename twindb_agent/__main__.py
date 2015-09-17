import logging
import optparse
import os
import sys
import signal
import twindb_agent.__about__
import twindb_agent.agent
import twindb_agent.config
import twindb_agent.globals
import twindb_agent.log


def get_opt_parser():
    parser = optparse.OptionParser(version=twindb_agent.__about__.__version__)
    parser.add_option("-d", "--dispatcher", help="IP address or hostname of TwinDB dispatcher")
    parser.add_option("-T", "--period", help="Period of time in seconds between repeating job requests", type="int")
    parser.add_option("-u", "--mysql_user", help="MySQL user")
    parser.add_option("-p", "--mysql_password", help="MySQL password")
    parser.add_option("--start", help="Start TwinDB agent", action="store_true", dest="start")
    parser.add_option("--stop", help="Stop TwinDB agent", action="store_true", dest="stop")
    parser.add_option("--register", help="Register TwinDB agent. "
                                         "Get your registration code on https://console.twindb.com/?get_code",
                      metavar="CODE", dest="reg_code")
    parser.add_option("--unregister", help="Unregister TwinDB agent", action="store_true", dest="unregister")
    parser.add_option("--delete-backups", help="When unregistering TwinDB agent delete backups taken from this server",
                      action="store_true", dest="delete_backups", default=False)
    parser.add_option("--is-registered", help="Check if the agent is registered in TwinDB", action="store_true")
    parser.add_option("--backup", help="Take backup copy now", action="store_true")
    parser.add_option("-g", "--debug", help="Print debug information",
                      action="store_true", dest="debug", default=False)

    return parser


def read_agent_config(options):
    try:
        agent_config = twindb_agent.config.AgentConfig.get_config(api_host=options.dispatcher,
                                                                  check_period=options.period,
                                                                  mysql_user=options.mysql_user,
                                                                  mysql_password=options.mysql_password)
        agent_config.save()
    except twindb_agent.config.AgentConfigException as err:
        print(err)
        sys.exit(2)


def main():
    opt_parser = get_opt_parser()
    (options, args) = opt_parser.parse_args()

    os.environ["PATH"] += ":/sbin:/usr/sbin"
    read_agent_config(options)

    # Create loggers
    twindb_agent.log.create_console_logger(options.debug)
    twindb_agent.log.create_local_logger(options.debug)
    twindb_agent.log.create_remote_logger(options.debug)

    console = logging.getLogger("twindb_console")

    agent = twindb_agent.agent.Agent()
    for sig in [signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGABRT, signal.SIGTERM]:
        signal.signal(sig, agent.stop)

    if options.start:
        agent.start()
    elif options.stop:
        console.warning("--stop is not implemented")
    elif options.reg_code:
        agent.register(options.reg_code)
    elif options.unregister:
        agent.unregister(options.delete_backups)
    elif options.backup:
        agent.backup()
    elif options.is_registered:
        console.debug("Checking TwinDB agent registration")
        if agent.is_registered():
            print("YES")
        else:
            print("NO")
    else:
        console.error("No command line arguments are given")
        opt_parser.print_help()
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
