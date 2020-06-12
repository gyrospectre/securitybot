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

from securitybot.exceptions import AuthException

from okta import UsersClient, FactorsClient
from okta.framework.ApiClient import ApiClient


class AuthClient(BaseAuthClient):

    def __init__(self, connection_config, reauth_time, auth_attrib) -> None:
        '''
        Args:
            connection_config (Dict):
                Parameters required to connect to the Okta API
            reauth_time (int):
                The min time in seconds to cache auth requests
            auth_attrib (str):
                The attribute of the user record that will be used to
                authenticate them.
        '''
        super().__init__(reauth_time, auth_attrib)
        connection_config['pathname'] = '/api/v1/users'

        self.usersclient = UsersClient(**connection_config)
        self.factorsclient = FactorsClient(**connection_config)
        self.apiclient = ApiClient(**connection_config)

        # Maintain a per user lookup for poll URL
        self.poll_url = {}

    def _get_okta_userid(self, username):
        user = self.usersclient.get_users(query=username, limit=1)

        try:
            return user[0].id
        except Exception as error:
            logging.error('Error getting username {}'.format(error))
            return None

    def _get_factors(self, userid):
        try:
            return self.factorsclient.get_lifecycle_factors(userid)
        except Exception as error:
            logging.error('Error getting factors {}'.format(error))
            return None

    def can_auth(self, user):
        # type: () -> bool
        # Check Okta user for a push factor.
        # Returns false is not available
        # Returns factor Id if it is
        # TODO: Add support for other types of auth (TOTP, etc).
        username = self._auth_attribute(user)
        if username is not False:
            logging.debug('Checking auth capabilities for {}'.format(username))

            okta_user_id = self._get_okta_userid(username)
            factors = self._get_factors(okta_user_id)
            if factors is not None:
                for factor in factors:
                    if factor.factorType == 'push':
                        return factor.id

        return False

    def auth(self, user, reason=None):
        # type: (str) -> None
        logging.debug(
            'Sending Okta Push request for {}'.format(
                self._auth_attribute(user)
            )
        )

        # Okta's SDK is broken!
        # https://github.com/okta/okta-sdk-python/issues/66
        # res = self.factorsclient.verify_factor(
        #    user_id=self.okta_user_id,
        #    user_factor_id=self.okta_push_factor_id
        # )
        # Implement our own call which actually works
        okta_user_id = self._get_okta_userid(self._auth_attribute(user))
        res = self.apiclient.post_path(
            '/{0}/factors/{1}/verify'.format(
                okta_user_id,
                user._factor_id
            )
        )
        try:
            res_obj = json.loads(res.text)
        except Exception as error:
            raise AuthException(error)

        self.poll_url[okta_user_id] = res_obj['_links']['poll']['href']
        user._last_auth_state = AuthStates.PENDING

    def auth_status(self, user):
        # type: () -> int
        okta_user_id = self._get_okta_userid(
            self._auth_attribute(user)
        )

        if user._last_auth_state == AuthStates.PENDING:
            response = self.apiclient.get(self.poll_url[okta_user_id])
            response_obj = json.loads(response.text)
            res = response_obj['factorResult']
            if res != 'WAITING':
                if res == 'SUCCESS':
                    user._last_auth_state = AuthStates.AUTHORIZED
                    user._last_auth_time = datetime.now(tz=pytz.utc)
                else:
                    user._last_auth_state = AuthStates.DENIED
                    user._last_auth_time = datetime.min
        elif user._last_auth_state == AuthStates.AUTHORIZED:
            if not self._recently_authed(user):
                user._last_auth_state = AuthStates.NONE
        return user._last_auth_state

    def reset(self, user):
        okta_user_id = self._get_okta_userid(
            self._auth_attribute(user)
        )
        self.poll_url.pop(okta_user_id, None)
        user._last_auth_state = AuthStates.NONE
