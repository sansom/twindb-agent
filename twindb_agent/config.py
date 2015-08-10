# -*- coding: utf-8 -*-

"""
Module to work with TwinDB agent config
"""
from __future__ import print_function
import os
import uuid
import twindb_agent.globals


class AgentConfig(object):
    _instance = None

    def __init__(self,
                 ssh_private_key_file=None,
                 ssh_public_key_file=None,
                 ssh_port=None,
                 pid_file=None,
                 check_period=None,
                 time_zone=None,
                 mysql_user=None,
                 mysql_password=None,
                 gpg_homedir=None,
                 api_email=None,
                 api_host=None,
                 api_proto=None,
                 api_dir=None,
                 api_uri=None,
                 api_pub_key=None
                 ):
        self.config_file = twindb_agent.globals.config_file

        self.ssh_private_key_file = twindb_agent.globals.ssh_private_key_file
        self.ssh_public_key_file = twindb_agent.globals.ssh_public_key_file
        self.ssh_port = twindb_agent.globals.ssh_port

        self.pid_file = twindb_agent.globals.pid_file
        self.check_period = twindb_agent.globals.check_period
        self.time_zone = twindb_agent.globals.time_zone

        self.mysql_user = twindb_agent.globals.mysql_user
        self.mysql_password = twindb_agent.globals.mysql_password

        self.gpg_homedir = twindb_agent.globals.gpg_homedir
        self.api_email = twindb_agent.globals.api_email
        self.api_host = twindb_agent.globals.api_host
        self.api_proto = twindb_agent.globals.api_proto
        self.api_dir = twindb_agent.globals.api_dir
        self.api_uri = twindb_agent.globals.api_uri
        self.api_pub_key = twindb_agent.globals.api_pub_key

        # Read the variables from agent config file (if it exists)
        try:
            if os.path.exists(self.config_file):
                global_vars = {}
                execfile(self.config_file, global_vars)
                for var in global_vars:
                    self.__dict__[var] = global_vars[var]

                # Legacy variable names
                # "host" is an old variable with dispatcher hostname
                if "host" in global_vars:
                    self.api_host = global_vars["host"]
                # init_config was renamed to config_file
                if "init_config" in global_vars:
                    self.config_file = global_vars["init_config"]
        except IOError as err:
            raise AgentConfigException("Failed to read config file %s. %s" % (self.config_file, err))
        except SyntaxError as err:
            raise AgentConfigException("Failed to read config file %s. %s" % (self.config_file, err))

        # Then read variables if they set via the constructor arguments
        if ssh_private_key_file:
            self.ssh_private_key_file = ssh_private_key_file

        if ssh_public_key_file:
            self.ssh_public_key_file = ssh_public_key_file

        if ssh_port:
            self.ssh_port = ssh_port

        if pid_file:
            self.pid_file = pid_file

        if check_period:
            self.check_period = check_period

        if time_zone:
            self.time_zone = time_zone

        if mysql_user:
            self.mysql_user = mysql_user

        if mysql_password:
            self.mysql_password = mysql_password

        if gpg_homedir:
            self.gpg_homedir = gpg_homedir

        if api_email:
            self.api_email = api_email

        if api_host:
            self.api_host = api_host

        if api_proto:
            self.api_proto = api_proto

        if api_dir:
            self.api_dir = api_dir

        if api_uri:
            self.api_dir = api_uri

        if api_pub_key:
            self.api_pub_key = api_pub_key

        # Create new server_id if it wasn't set by the config file
        if "server_id" not in self.__dict__:
            self.server_id = str(uuid.uuid4())

    def save(self):
        """
        Saves server_id variable in file init_config (/etc/twindb.cfg)
        :return: True    - if config was successfully saved
        Exits if error happened
        """
        try:
            f = open(self.config_file, "w")
            for var in self.__dict__:
                var = str(var)
                if not var.startswith("__") and var not in ["mysql_user", "mysql_password"]:
                    if isinstance(self.__dict__[var], int):
                        f.write("%s = %d\n" % (var, self.__dict__[var]))
                    else:
                        if "\n" in self.__dict__[var]:
                            f.write("%s = \"\"\"%s\"\"\"\n" % (var, self.__dict__[var]))
                        else:
                            f.write("%s = \"%s\"\n" % (var, self.__dict__[var]))
            f.close()
        except IOError as err:
            raise AgentConfigException("Failed to save new config in %s. %s" % (self.config_file, err))
        return True

    @staticmethod
    def get_config(ssh_private_key_file=None,
                   ssh_public_key_file=None,
                   ssh_port=None,
                   pid_file=None,
                   check_period=None,
                   time_zone=None,
                   mysql_user=None,
                   mysql_password=None,
                   gpg_homedir=None,
                   api_email=None,
                   api_host=None,
                   api_proto=None,
                   api_dir=None,
                   api_uri=None,
                   api_pub_key=None):
        if not AgentConfig._instance:
            AgentConfig._instance = AgentConfig(ssh_private_key_file,
                                                ssh_public_key_file,
                                                ssh_port,
                                                pid_file,
                                                check_period,
                                                time_zone,
                                                mysql_user,
                                                mysql_password,
                                                gpg_homedir,
                                                api_email,
                                                api_host,
                                                api_proto,
                                                api_dir,
                                                api_uri,
                                                api_pub_key)

        return AgentConfig._instance


class AgentConfigException(Exception):
    pass
