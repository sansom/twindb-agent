# -*- coding: utf-8 -*-

import optparse
import sys
import twindb_agent.__about__
import twindb_agent.agent
import twindb_agent.config
import twindb_agent.globals


def parse_options():
    parser = optparse.OptionParser()
    parser.add_option("-d", "--dispatcher", help="IP address or hostname of TwinDB dispatcher",
                      default=twindb_agent.globals.api_host)
    parser.add_option("-T", "--period", help="Period of time in seconds between repeating job requests",
                      default=twindb_agent.globals.check_period)
    parser.add_option("-u", "--mysql_user", help="MySQL user",
                      default=twindb_agent.globals.mysql_user)
    parser.add_option("-p", "--mysql_password", help="MySQL password",
                      default=twindb_agent.globals.mysql_password)
    parser.add_option("--start", help="Start TwinDB agent", action="store_true", dest="start")
    parser.add_option("--stop", help="Stop TwinDB agent", action="store_true", dest="stop")
    parser.add_option("--register", help="Register TwinDB agent")
    parser.add_option("--unregister", help="Unregister TwinDB agent", action="store_true", dest="unregister")
    parser.add_option("--delete-backups", help="When unregistering TwinDB agent delete backups taken from this server",
                      action="store_true", dest="delete_backups", default=False)
    parser.add_option("--backup", help="Take backup copy now")
    parser.add_option("--is-registered", help="Check if the agent is registered in TwinDB")
    parser.add_option("--version", help="Print the agent version", action="store_true")
    return parser.parse_args()


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
    (options, args) = parse_options()

    agent_config = get_agent_config(options)
    agent = twindb_agent.agent.Agent(agent_config)

    if options.start:
        agent.start()
    elif options.stop:
        agent.stop()
    elif options.register:
        agent.register()
    elif options.unregister:
        agent.unregister(options.delete_backups)
    elif options.backup:
        agent.backup()
    elif options.is_registered:
        agent.is_registered()
    elif options.version:
        print(twindb_agent.__version__)
        sys.exit(0)
    else:
        sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
