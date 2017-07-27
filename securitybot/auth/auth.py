'''
An authentication object for doing 2FA on Slack users.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

from datetime import timedelta
from abc import ABCMeta, abstractmethod
from enum import Enum, unique


@unique
class AuthStates(Enum):
    NONE = 1
    PENDING = 2
    AUTHORIZED = 3
    DENIED = 4


class Auth(object, metaclass=ABCMeta):
    '''
    When designing Auth subclasses, try to make sure that the authorization
    attempt is as non-blocking as possible.
    '''

    @abstractmethod
    def __init__(self, config: dict=None, **kwargs):
        '''
        Initialise default values for global config
        '''
        if config is None:
            return
        self.auth_time = timedelta(seconds=config.get('auth_time', 7200))

    @abstractmethod
    def can_auth(self) -> bool:
        '''
        Returns:
            (bool) Whether 2FA is available.
        '''
        raise NotImplementedError()

    @abstractmethod
    def auth(self, reason: str=None) -> None:
        '''
        Begins an authorization request, which should be non-blocking.

        Args:
            reason (str): Optional reason string that may be provided
        '''
        raise NotImplementedError()

    @abstractmethod
    def auth_status(self) -> int:
        '''
        Returns:
            (enum) The current auth status, one of AUTH_STATES.
        '''
        raise NotImplementedError()

    @abstractmethod
    def reset(self) -> None:
        '''
        Resets auth status.
        '''
        raise NotImplementedError()
