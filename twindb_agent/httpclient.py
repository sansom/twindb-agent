# -*- coding: utf-8 -*-

"""
Class that communicates to TwinDB dispatcher
"""
import httplib
import json
import socket
import urllib
import twindb_agent.logging_local
import twindb_agent.gpg


class TwinDBHTTPClient(object):
    def __init__(self, config, debug=False):
        self.config = config
        self.debug = debug

        self.logger = twindb_agent.logging_local.getlogger(__name__, debug)

    def get_response(self, request):
        """
        Sends HTTP POST request to TwinDB dispatcher
        It converts python data structure in "data" variable into JSON string,
        then encrypts it and then sends as variable "data" in HTTP request
        Inputs
            uri     - URI to send the request
            data    - Data structure with variables
        Returns
            String with body of HTTP response
            None    - if error happened or empty response
        """
        log = self.logger
        response_body = None

        log.debug("Enter get_response(uri=" + self.config.api_uri + ")")
        if self.config.api_proto == "http":
            conn = httplib.HTTPConnection(self.config.api_host)
        elif self.config.api_proto == "https":
            conn = httplib.HTTPSConnection(self.config.api_host)
        else:
            raise TwinDBHTTPClientException("Unsupported protocol " + self.config.api_proto)

        url = self.config.api_proto + "://" + self.config.api_host + "/" + self.config.api_dir + "/" + \
            self.config.api_uri
        http_response = "Empty response"
        try:
            conn.connect()
            log.debug("Sending to " + self.config.api_host + ": %s" % json.dumps(request, indent=4, sort_keys=True))
            data_json = json.dumps(request)
            gpg = twindb_agent.gpg.TwinDBGPG(self.config)
            data_json_enc = gpg.encrypt(data_json)
            data_json_enc_urlenc = urllib.urlencode({'data': data_json_enc})
            conn.putrequest('POST', "/" + self.config.api_dir + "/" + self.config.api_uri)
            headers = dict()
            headers['Content-Length'] = "%d" % (len(data_json_enc_urlenc))
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            for k in headers:
                conn.putheader(k, headers[k])
            conn.endheaders()
            conn.send(data_json_enc_urlenc)
            http_response = conn.getresponse()

            if http_response.status == 200:
                response_body = http_response.read()
                log.debug("Response body: '%s'" % response_body)
                if len(response_body) == 0:
                    return None
                url = "%(proto)s://%(host)s/%(api_dir)s/%(uri)s" % {
                    "proto": self.config.api_proto,
                    "host": self.config.api_host,
                    "api_dir": self.config.api_dir,
                    "uri": self.config.api_uri
                }
                d = json.JSONDecoder()
                try:
                    json.loads(response_body)
                except ValueError:
                    msg = response_body
                else:
                    msg = json.dumps(d.decode(response_body), indent=4, sort_keys=True)
                log.debug("Response from %(url)s : '%(resp)s'" % {
                    "url": url,
                    "resp": msg
                })
            else:
                log.error("HTTP error %d %s" % (http_response.status, http_response.reason))
        except socket.error as err:
            log.error("Exception while making request " + url)
            log.error(err)
            log.error("TwinDB dispatcher is unreachable")
            return None
        except KeyError as err:
            log.error("Failed to decode response from server: %s" % http_response)
            log.error("Could not find key %s" % err)
            return None
        except httplib.BadStatusLine as err:
            log.error("Exception while making request %s: %s" % (url, err))
            return None
        finally:
            conn.close()
        return response_body


class TwinDBHTTPClientException(Exception):
    pass


class TwinDBHTTPClientLoggingException(Exception):
    pass
