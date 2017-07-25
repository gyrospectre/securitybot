'''
An authentication object for doing 2FA on Slack users.
'''
__author__ = 'Alex Bertsch'
__email__ = 'abertsch@dropbox.com'

from datetime import timedelta
from abc import ABCMeta, abstractmethod
from enum import Enum, unique


@unique
class AuthState(Enum):
    NONE = 1
    PENDING = 2
    AUTHORIZED = 3
    DENIED = 4


class Auth(object):
    '''
    When designing Auth subclasses, try to make sure that the authorization
    attempt is as non-blocking as possible.
    '''
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, config: dict=None, **kwargs):
        '''
        Initialise default values for global config
        '''
        if dict is None:
            return
        self.auth_time = timedelta(seconds=config.get('auth_time', 7200))

    @abstractmethod
    def can_auth(self) -> bool:
        '''
        Returns:
            (bool) Whether 2FA is available.
        '''
        pass

    @abstractmethod
    def auth(self, reason: str=None) -> None:
        '''
        Begins an authorization request, which should be non-blocking.

        Args:
            reason (str): Optional reason string that may be provided
        '''
        pass

    @abstractmethod
    def auth_status(self) -> int:
        '''
        Returns:
            (enum) The current auth status, one of AUTH_STATES.
        '''
        pass

    @abstractmethod
    def reset(self) -> None:
        '''
        Resets auth status.
        '''
        pass
