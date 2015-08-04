# -*- coding: utf-8 -*-

import optparse
import sys
import twindb_agent.__about__
import twindb_agent.agent
import twindb_agent.config
import twindb_agent.globals


def get_opt_parser():
    parser = optparse.OptionParser(version=twindb_agent.__about__.__version__)
    parser.add_option("-d", "--dispatcher", help="IP address or hostname of TwinDB dispatcher",
                      default=twindb_agent.globals.api_host)
    parser.add_option("-T", "--period", help="Period of time in seconds between repeating job requests",
                      default=twindb_agent.globals.check_period,
                      type="int")
    parser.add_option("-u", "--mysql_user", help="MySQL user",
                      default=twindb_agent.globals.mysql_user)
    parser.add_option("-p", "--mysql_password", help="MySQL password",
                      default=twindb_agent.globals.mysql_password)
    parser.add_option("--start", help="Start TwinDB agent", action="store_true", dest="start")
    parser.add_option("--stop", help="Stop TwinDB agent", action="store_true", dest="stop")
    parser.add_option("--register", help="Register TwinDB agent. "
                                         "Get your registration code on https://console.twindb.com/?get_code",
                      metavar="CODE", dest="reg_code")
    parser.add_option("--unregister", help="Unregister TwinDB agent", action="store_true", dest="unregister")
    parser.add_option("--delete-backups", help="When unregistering TwinDB agent delete backups taken from this server",
                      action="store_true", dest="delete_backups", default=False)
    parser.add_option("--is-registered", help="Check if the agent is registered in TwinDB", action="store_true")
    parser.add_option("--backup", help="Take backup copy now")
    parser.add_option("--debug", help="Print debug information to log",
                      action="store_true", dest="debug", default=False)

    return parser


def get_agent_config(options):
    try:
        agent_config = twindb_agent.config.AgentConfig(api_host=options.dispatcher,
                                                       check_period=options.period,
                                                       mysql_user=options.mysql_user,
                                                       mysql_password=options.mysql_password)
        agent_config.save()
    except twindb_agent.config.AgentConfigException as err:
        print(err)
        sys.exit(2)
    return agent_config


def main():
    opt_parser = get_opt_parser()
    (options, args) = opt_parser.parse_args()

    agent_config = get_agent_config(options)
    agent = twindb_agent.agent.Agent(agent_config, debug=options.debug)

    if options.start:
        agent.start()
    elif options.stop:
        agent.stop()
    elif options.reg_code:
        agent.register(options.reg_code)
    elif options.unregister:
        agent.unregister(options.delete_backups)
    elif options.backup:
        agent.backup()
    elif options.is_registered:
        if agent.is_registered():
            print("YES")
        else:
            print("NO")
    else:
        opt_parser.print_help()
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
