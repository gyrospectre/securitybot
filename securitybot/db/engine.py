'''
An abstract to the db backend
'''

__author__ = 'Antoine Cardon'
__email__ = 'antoine.cardon@algolia.com'

from typing import Any, List, Dict
from securitybot.utils.class_helper import Singleton
from abc import ABCMeta, abstractmethod

engines = {}


def register_engine(cls):
    engines[cls.__name__] = cls
    return cls


class EngineInterface(object, metaclass=ABCMeta):

    @abstractmethod
    def __init__(self, config: Dict[str, Any], **kwargs):
        '''
        Initializes the DB backend with the config dictionnary.

        Args:
            config (dict): The configuration forn the database. This may contains implementation specific paramters
        '''
        raise NotImplementedError()

    @abstractmethod
    def execute(query: str, params: List[Any]=None):
        '''
        Instructs the backend to run the following query and return a list of results.
        '''
        raise NotImplementedError()


class EngineException(Exception):
    pass


class DbEngine(object, metaclass=Singleton):

    def __init__(self, config: Dict[str, Any]=None):
        if config.get('engine', None) not in engines.keys():
            raise EngineException("Engine not found")
        else:
            self._engine: EngineInterface = engines[config['engine']](config)

    def execute(self, query: str, params: List[Any]=None):
        return self._engine.execute(query, params)
