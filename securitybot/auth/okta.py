'''
Authentication using Okta.
'''
import pytz

__author__ = 'Chandler Newby, Bill Mahony'
__email__ = 'chandler.newby@gmail.com, paranoid@none.xyz'

import logging
import json

from datetime import datetime

from securitybot.auth.auth import BaseAuthClient, AuthStates

from okta import UsersClient, FactorsClient
from okta.framework.ApiClient import ApiClient


class AuthClient(BaseAuthClient):

    def __init__(self, connection_config, username="") -> None:
        '''
        Args:
            connection_config (Dict): Parameters required to connect to the Okta API
            username (str): The username of the person authorized through
                            this object.
        '''
        super().__init__()
        connection_config['pathname'] = '/api/v1/users'

        self.usersclient = UsersClient(**connection_config)
        self.factorsclient = FactorsClient(**connection_config)
        self.apiclient = ApiClient(**connection_config)

        self.username: str = username
        self.username = "hard.code" # Testing against Okta user that doesn't match Slack
        self.auth_time = datetime.min
        self.state = AuthStates.NONE
        self.okta_user_id = None
        self.okta_push_factor_id = None
        self.poll_url = None
        self.state = AuthStates.NONE

    def _get_okta_userid(self, username):
        user = self.usersclient.get_users(query=username, limit=1)
        
        try:
            return user[0].id
        except:
            return None

    def _get_factors(self, userid):
        return self.factorsclient.get_lifecycle_factors(userid)

    def can_auth(self):
        # type: () -> bool
        # Check Okta user for a push factor.
        # TODO: Add support for other types of auth (TOTP, etc).
        logging.debug('Checking auth capabilities for {}'.format(self.username))

        self.okta_user_id = self._get_okta_userid(self.username)
        factors = self._get_factors(self.okta_user_id)
        for factor in factors:
            if factor.factorType == 'push':
                self.okta_push_factor_id = factor.id
                return True

        return False

    def auth(self, reason=None):
        # type: (str) -> None
        logging.debug('Sending Okta Push request for {}'.format(self.username))

        ## Oktas SDK is broken! https://github.com/okta/okta-sdk-python/issues/66
        #res = self.factorsclient.verify_factor(
        #    user_id=self.okta_user_id,
        #    user_factor_id=self.okta_push_factor_id
        #)
        ## Implement our own call which actually works
        res = self.apiclient.post_path('/{0}/factors/{1}/verify'.format(self.okta_user_id, self.okta_push_factor_id))
        res_obj = json.loads(res.text)
        self.poll_url = res_obj['_links']['poll']['href']
        self.state = AuthStates.PENDING

    def _recently_authed(self):
        # type: () -> bool
        return (datetime.now(tz=pytz.utc) - self.auth_time) < self.reauth_time

    def auth_status(self):
        # type: () -> int
        if self.state == AuthStates.PENDING:
            response = self.apiclient.get(self.poll_url)
            response_obj = json.loads(response.text)
            res = response_obj['factorResult']
            if res != 'WAITING':
                if res == 'SUCCESS':
                    self.state = AuthStates.AUTHORIZED
                    self.auth_time = datetime.now(tz=pytz.utc)
                else:
                    self.state = AuthStates.DENIED
                    self.auth_time = datetime.min
        elif self.state == AuthStates.AUTHORIZED:
            if not self._recently_authed():
                self.state = AuthStates.NONE
        return self.state

    def reset(self):
        # type: () -> None
        self.poll_url = None
        self.state = AuthStates.NONE
