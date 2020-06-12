'''
An abstract to the db backend
'''

__author__ = 'Antoine Cardon, Bill Mahony'
__email__ = 'antoine.cardon@algolia.com, xxx@xxx.xx'

from typing import Any, List, Dict
from abc import ABCMeta, abstractmethod


class BaseDbClient(object, metaclass=ABCMeta):
    '''
    A wrapper over various database frameworks, like MySQL.
    '''
    @abstractmethod
    def __init__(self, config: Dict[str, Any], **kwargs):
        '''
        Initializes the DB backend with the config dictionnary.

        Args:
            config (dict):
                The configuration forn the database. This may contains
                implementation specific paramters
        '''
        raise NotImplementedError()

    @abstractmethod
    def execute(self, query: str, params: List[Any] = None):
        '''
        Instructs the backend to run the following query
        and return a list of results.
        '''
        raise NotImplementedError()
