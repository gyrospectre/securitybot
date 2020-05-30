'''
Authentication using Duo.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Callable

from securitybot.auth.auth import Auth, AuthStates
from securitybot.config import config


class DuoAuth(Auth):

    def __init__(self, duo_api: Callable=None, username="") -> None:
        '''
        Args:
            duo_api (duo_client.Auth): An Auth API client from Duo.
            username (str): The username of the person authorized through
                            this object.
        '''
        super().__init__()
        self.client: Callable = duo_api
        self.username: str = username
        self.txid: str = None
        self.auth_time = datetime.min
        self.reauth_time = config['auth']['reauth_time']
        self.state = AuthStates.NONE

    def can_auth(self) -> bool:
        # Use Duo preauth to look for a device with Push
        # TODO: This won't work for anyone who's set to auto-allow, but
        # I don't believe we have anyone like that...
        logging.debug('Checking auth capabilities for {}'.format(self.username))
        res = self.client.preauth(username=self.username)
        if res['result'] == 'auth':
            for device in res['devices']:
                if 'push' in device['capabilities']:
                    return True
        return False

    def auth(self, reason: str=None) -> None:
        logging.debug('Sending Duo Push request for {}'.format(self.username))
        pushinfo = 'from=Securitybot'
        if reason:
            pushinfo += '&'
            pushinfo += urlencode({'reason': reason})

        res = self.client.auth(
            username=self.username,
            async=True,
            factor='push',
            device='auto',
            type='Securitybot',
            pushinfo=pushinfo
        )
        self.txid = res['txid']
        self.state = AuthStates.PENDING

    def _recently_authed(self) -> bool:
        return (datetime.now() - self.auth_time) < self.reauth_time

    def auth_status(self) -> int:
        if self.state == AuthStates.PENDING:
            res = self.client.auth_status(self.txid)
            if not res['waiting']:
                if res['success']:
                    self.state = AuthStates.AUTHORIZED
                    self.auth_time = datetime.now()
                else:
                    self.state = AuthStates.DENIED
                    self.auth_time = datetime.min
        elif self.state == AuthStates.AUTHORIZED:
            if not self._recently_authed():
                self.state = AuthStates.NONE
        return self.state

    def reset(self) -> None:
        self.txid = None
        self.state = AuthStates.NONE
