import json
import logging
import twindb_agent.gpg
import twindb_agent.httpclient


class TwinDBAPI(object):
    """
    Class TwinDBAPI implements communication with dispatcher
    """
    def __init__(self, logger_name="twindb_remote"):
        self.http = twindb_agent.httpclient.TwinDBHTTPClient(logger_name=logger_name)
        self.gpg = twindb_agent.gpg.TwinDBGPG(logger_name=logger_name)
        self.logger = logging.getLogger(logger_name)
        self.success = None
        self.response = None
        self.data = None
        self.error = None
        self.debug = None

    def call(self, data):
        log = self.logger

        response_body = self.http.get_response(data)
        if not response_body:
            self.success = False
            log.error("Empty response from dispatcher")
            return None
        try:
            response_body_decoded = json.JSONDecoder().decode(response_body)
        except ValueError as err:
            self.success = False
            log.error(err)
            return None
        try:
            self.success = response_body_decoded["success"]
            self.response = response_body_decoded["response"]
        except KeyError as err:
            self.success = False
            log.error(err)
            return None

        if self.response:
            response_decrypted = self.gpg.decrypt(self.response)
        else:
            response_decrypted = None
        log.debug("API response:\n%s" % json.dumps(response_decrypted, indent=4, sort_keys=True))
        try:
            self.data = json.JSONDecoder().decode(response_decrypted)["data"]
        except TypeError:
            self.data = None
        try:
            self.error = json.JSONDecoder().decode(response_decrypted)["error"]
        except TypeError:
            self.error = None
        try:
            self.debug = json.JSONDecoder().decode(response_decrypted)["debug"]
        except TypeError:
            self.debug = None

        if not self.success:
            log.warning("Unsucessfull TwinDB API call")
            log.error(self.error)
            log.debug(self.debug)

        return self.data
