'''
An authentication object for doing 2FA on Slack users.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import pytz

from datetime import datetime, timedelta

from abc import ABCMeta, abstractmethod

from enum import Enum, unique


@unique
class AuthStates(Enum):
    NONE = 1
    PENDING = 2
    AUTHORIZED = 3
    DENIED = 4


class BaseAuthClient(object, metaclass=ABCMeta):
    '''
    When designing Auth subclasses, try to make sure that the authorization
    attempt is as non-blocking as possible.
    '''

    @abstractmethod
    def __init__(self, reauth_time, auth_attrib):
        '''
        Initialise default values for global config
        '''
        self.reauth_time = reauth_time
        self.auth_attrib = auth_attrib
        self.auth_time = timedelta(seconds=self.reauth_time)

    def _auth_attribute(self, user):
        # Return the attribute of a User object that
        # will be used to match to the auth platform.
        if self.auth_attrib == 'username':
            return user['name']
        elif user.get_email() and self.auth_attrib == 'email':
            return user.get_email()
        elif user.get_displayname() and self.auth_attrib == 'displayname':
            return user.get_displayname()

        return False

    @abstractmethod
    def can_auth(self) -> bool:
        '''
        Returns:
            (bool) Whether 2FA is available.
        '''
        raise NotImplementedError()

    @abstractmethod
    def auth(self, reason: str = None) -> None:
        '''
        Begins an authorization request, which should be non-blocking.

        Args:
            reason (str): Optional reason string that may be provided
        '''
        raise NotImplementedError()

    def _recently_authed(self, user):
        # type: () -> bool
        return (
            (datetime.now(tz=pytz.utc) - user._last_auth_time) <
            timedelta(seconds=self.reauth_time)
        )

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
