"""
Module to work with TwinDB agent config
"""
from __future__ import print_function
import os
import twindb.globals


class AgentConfig(object):
    def __init__(self, config=twindb.globals.init_config,
                 host=twindb.globals.host,
                 api_pub_key=twindb.globals.api_pub_key):
        self.config = config
        self.server_id = None
        self.host = host
        self.api_pub_key = api_pub_key

    def read(self):
        """
        Reads config from /etc/twindb.cfg and sets server_id variable
        :return: True if config was successfully read
        Exits if error happened
        """
        try:
            if os.path.exists(self.config):
                ns = {}
                execfile(self.config, ns)
                if "server_id" in ns:
                    self.server_id = ns["server_id"]
                else:
                    raise AgentConfigException("Config %s doesn't set server_id" % self.config)
                if "host" in ns:
                    self.host = ns["host"]
                if "api_pub_key" in ns:
                    self.api_pub_key = ns["api_pub_key"]
            else:
                raise AgentConfigException("Config %s doesn't exist" % self.config)
        except IOError as err:
            raise AgentConfigException("Failed to read config file %s. %s" % (self.config, err))
        return True

    def save(self):
        """
        Saves server_id variable in file init_config (/etc/twindb.cfg)
        :return: True    - if config was successfully saved
        Exits if error happened
        """
        if not self.server_id:
            raise AgentConfigException("Can not save agent config file because server_id is empty")
        try:
            f = open(self.config, "w")
            f.write("server_id='%s'\n" % self.server_id)
            f.write("host='%s'\n" % self.host)
            f.write("api_pub_key=\"\"\"%s\"\"\"\n" % self.api_pub_key)
            f.close()
        except IOError as err:
            raise AgentConfigException("Failed to save new config in %s. %s" % (self.config, err))
        return True

    def set_server_id(self, server_id):
        self.server_id = server_id

    def set_host(self, host):
        self.host = host

    def set_api_pub_key(self, key):
        self.api_pub_key = key

    def get_server_id(self):
        return self.server_id

    def get_host(self):
        return self.host

    def get_api_pub_key(self):
        return self.api_pub_key


class AgentConfigException(Exception):
    pass