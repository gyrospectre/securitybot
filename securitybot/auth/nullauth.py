'''
Dummy authenticator which returns always True.
'''
__author__ = 'Antoine Cardon'
__email__ = 'antoine.cardon@algolia.com'

from securitybot.auth.auth import Auth


class NullAuth(Auth):

    def __init__(self) -> None:
        pass

    def can_auth(self) -> bool:
        return False

    def auth(self, reason: str=None) -> None:
        pass

    def _recently_authed(self) -> str:
        # type: () -> bool
        return 'AUTHORIZED'

    def auth_status(self) -> bool:
        return True

    def reset(self) -> None:
        pass
