'''
Dummy authenticator which returns always True.
'''
__author__ = 'Antoine Cardon'
__email__ = 'antoine.cardon@algolia.com'

from securitybot.auth.auth import BaseAuthClient, AuthStates


class AuthClient(BaseAuthClient):

    def __init__(self, connection_config, reauth_time, auth_attrib) -> None:
        pass

    def can_auth(self, user) -> bool:
        return False

    def auth(self, user, reason: str=None) -> None:
        pass

    def _recently_authed(self, user) -> str:
        # type: () -> bool
        return AuthStates.AUTHORIZED

    def auth_status(self, user) -> bool:
        return True

    def reset(self, user) -> None:
        pass
