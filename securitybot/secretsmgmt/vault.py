'''
Password management using Hashicorp Vault
'''

__author__ = 'Bill Mahony'


import os
import logging

from securitybot.secretsmgmt.secretsmgmt import BaseSecretsClient

from securitybot.exceptions import SecretsException

from hvac import Client


class SecretsClient(BaseSecretsClient):

    def __init__(self, connection_config) -> None:
        '''
        Args:
            connection_config (Dict): Parameters required to connect to the Vault
        '''
        try:
            token = os.environ[connection_config['token_env']]
        except KeyError as error:
            raise SecretsException(
                'Token environment variable missing: {}'.format(error)
            )
        self._client = Client(
            url=connection_config['url'],
            token=token
        )
        if not self._client.is_authenticated():
            raise SecretsException('Vault client authentication failed!')
        else:
            logging.debug('Sucessfully connected to Vault.')

    def get_secret(self, secret):
        read_response = self._client.secrets.kv.read_secret_version(path=secret)

        return read_response['data']['data']

    def create_secret(self, name, value, description=None):
        create_response = self._client.secrets.kv.v2.create_or_update_secret(
            path=name,
            secret=value
        )
        logging.debug("Wrote secret to path {}".format(name))
        if create_response['warnings'] is not None:
            logging.debug('with warnings {}'.format(create_response['warnings']))

