'''
A wrapper over an abstract secrets management system.
'''
__author__ = 'Bill Mahony'

from abc import ABCMeta, abstractmethod


class BaseSecretsClient(object, metaclass=ABCMeta):
    '''
    A wrapper over various secrets management frameworks, like Vault.
    '''

    @abstractmethod
    def __init__(self, reauth_time, auth_attrib):
        '''
        Initialise default values for global config and
        connects to the secrets management system.
        '''
        pass

    @abstractmethod
    def get_secret(self, secret):
        '''Fetch a secret from the backend'''
        pass

    @abstractmethod
    def create_secret(self, name, value, description):
        '''Store a new secret in the backend'''
        pass
