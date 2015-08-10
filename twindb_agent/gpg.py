# -*- coding: utf-8 -*-

"""
Classes and functions for cryptography
"""
from base64 import b64encode, b64decode
import logging
import os
import subprocess
import twindb_agent.config


class TwinDBGPG(object):
    def __init__(self):
        self.config = twindb_agent.config.AgentConfig.get_config()
        self.logger = logging.getLogger("twindb_local")
        self.check_gpg()

    def is_gpg_key_installed(self, email, key_type="public"):
        """
        Checks if TwinDB API public key is installed
        Returns
        True    - if the key is installed
        False   - if not
        """
        log = self.logger
        if not email:
            log.error("Can not check public key of an empty email")
            return False
        log.debug("Checking if public key of %s is installed" % email)
        gpg_cmd = ["gpg", "--homedir", self.config.gpg_homedir]
        try:
            if key_type == "public":
                gpg_cmd.append("-k")
            else:
                gpg_cmd.append("-K")
            gpg_cmd.append(email)
            log.debug(gpg_cmd)
            devnull = open("/dev/null", "w")
            ret = subprocess.call(gpg_cmd, stdout=devnull, stderr=devnull)
            devnull.close()
            if ret != 0:
                log.debug("GPG returned %d" % ret)
                log.debug(key_type + " key " + email + " is NOT installed")
                result = False
            else:
                log.debug(key_type + " key is already installed")
                result = True
        except OSError as err:
            raise TwinDBGPGException("Couldn't run command %r. %s" % (gpg_cmd, err))
            # exit_on_error("Couldn't get %s key of %s." % (key_type, email))
        return result

    def install_api_pub_key(self):
        """
        Installs TwinDB public key
        Returns
          True    - if the key is successfully installed
        Exits if the key wasn't installed
        """
        log = self.logger
        log.info("Installing %s public key" % self.config.api_email)
        gpg_cmd = ["gpg", "--homedir", self.config.gpg_homedir, "--import"]
        try:
            p = subprocess.Popen(gpg_cmd, stdin=subprocess.PIPE)
            p.communicate(self.config.api_pub_key)
        except OSError as err:
            raise TwinDBGPGException("Couldn't run command %r. %s" % (gpg_cmd, err))
            # exit_on_error("Couldn't install TwinDB public key")
        log.info("Twindb public key successfully installed")
        return True

    def check_gpg(self):
        """
        Checks if GPG environment is good to start TwinDB agent
        Installs TwinDB public key if necessary
        Returns
          True    - if the GPG environment good to proceed
        Exits if GPG wasn't configured correctly
        """
        log = self.logger
        log.debug("Checking if GPG config is initialized")
        if os.path.exists(self.config.gpg_homedir):
            if not self.is_gpg_key_installed(self.config.api_email):
                self.install_api_pub_key()
            else:
                log.debug("Twindb public key is already installed")
        else:
            log.info("Looks like GPG never ran. Initializing GPG configuration")
            try:
                os.mkdir(self.config.gpg_homedir, 0700)
                self.install_api_pub_key()
            except OSError as err:
                log.error("Failed to create directory %s. %s" % (self.config.gpg_homedir, err))
                raise TwinDBGPGException("Couldn't create directory " + self.config.gpg_homedir)
        email = "%s@twindb.com" % self.config.server_id
        if not (self.is_gpg_key_installed(email) and self.is_gpg_key_installed(email, "private")):
            self.gen_entropy()
            self.gen_gpg_keypair("%s@twindb.com" % self.config.server_id)
        log.debug("GPG config is OK")
        return True

    @staticmethod
    def gen_entropy():
        """
        Checks how much entropy is available in the system
        If not enough, does some disk activity to generate more
        """
        # Do nothing until I find good way to generate entropy
        return

    def gen_gpg_keypair(self, email):
        """
        Generates GPG private and public keys for a given recipient
        Inputs
          email   - recipient
        Returns
          True on success or exits
        """
        log = self.logger
        if not email:
            raise TwinDBGPGException("Can not generate GPG keypair for an empty email")
        gpg_cmd = ["gpg", "--homedir", self.config.gpg_homedir, "--batch", "--gen-key"]
        try:
            log.info("The agent needs to generate cryptographically strong keys.")
            log.info("Generating GPG keys pair for %s" % email)
            log.info("It may take really, really long time. Please be patient.")
            self.gen_entropy()
            gpg_script = """
%%echo Generating a standard key
Key-Type: RSA
Key-Length: 2048
Subkey-Type: RSA
Subkey-Length: 2048
Name-Real: Backup Server id %s
Name-Comment: No passphrase
Name-Email: %s
Expire-Date: 0
%%commit
%%echo done
    """ % (self.config.server_id, email)

            p = subprocess.Popen(gpg_cmd, stdin=subprocess.PIPE)
            p.communicate(gpg_script)
        except OSError as err:
            raise TwinDBGPGException("Failed to run command %r. %s" % (gpg_cmd, err))
            # exit_on_error("Failed to generate GPG keys pair")
        return True

    def encrypt(self, msg):
        """
        Encrypts message with TwinDB public key
        If server_id is non-zero (which means the server is registered)
        signs the message with the server's private key
        :param msg: string to encrypt
        :return:  64-base encoded and encrypted message or None if error happens.
        To read the encrypted message - decrypt and 64-base decode
        """
        log = self.logger
        server_email = "%s@twindb.com" % self.config.server_id
        enc_cmd = ["gpg", "--homedir", self.config.gpg_homedir, "-r", self.config.api_email, "--batch",
                   "--trust-model", "always",
                   "--armor", "--sign", "--local-user", server_email, "--encrypt"]
        cout = "No output"
        cerr = "No output"
        try:
            log.debug("Encrypting message:")
            log.debug(msg)
            log.debug("Encryptor command: ")
            log.debug(enc_cmd)
            p = subprocess.Popen(enc_cmd,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            cout, cerr = p.communicate(msg)
            if p.returncode != 0:
                raise OSError(p.returncode)
            ct = cout
            ct_64 = b64encode(ct)
            log.debug("Encrypted message: " + ct_64)
        except OSError as err:
            log.error("Failed to run command %r. %s" % (enc_cmd, err))
            log.error("Failed to encrypt message: " + msg)
            log.error("STDOUT: " + cout)
            log.error("STDERR: " + cerr)
            return None
        return ct_64

    def decrypt(self, msg_64):
        """
        Decrypts message with local private key
        :param msg_64: 64-base encoded and encrypted message. Before encryption the message was 64-base encoded
        :return: Plain text message or None if error happens
        """
        log = self.logger
        if not msg_64:
            log.error("Will not decrypt empty message")
            return None
        cout = "No output"
        cerr = "No output"
        gpg_cmd = ["gpg", "--homedir", self.config.gpg_homedir, "-d", "-q"]
        try:
            log.debug("Decrypting message:")
            log.debug(msg_64)
            log.debug("Decryptor command:")
            log.debug(gpg_cmd)
            p = subprocess.Popen(gpg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            msg = b64decode(msg_64)
            cout, cerr = p.communicate(msg)
            if p.returncode != 0:
                raise OSError(p.returncode)
        except OSError as err:
            log.error("Failed to run command %r. %s" % (gpg_cmd, err))
            log.error("Failed to decrypt message: " + msg_64)
            log.error("STDOUT: " + cout)
            log.error("STDERR: " + cerr)
            return None
        log.debug("Decrypted message:")
        log.debug(cout)
        return cout


class TwinDBGPGException(Exception):
    pass
