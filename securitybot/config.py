__author__ = 'Antoine Cardon'
__email__ = 'antoine.cardon@algolia.com'

import yaml
import logging
from typing import Dict
from securitybot.utils.class_helper import Singleton


class Config(object, metaclass=Singleton):

    def __init__(self, *args, **kwargs):
        self._config = {}

    def load_config(self, config_path: str="") -> Dict:
        logging.info('Loading configuration.')
        with open(config_path, 'r') as f:
            self._config = yaml.safe_load(f)
            self._config['queries'] = {}
            try:
                self._config['messages'] = yaml.safe_load(
                    open(self._config['includes']['messages_path']))
                self._config['commands'] = yaml.safe_load(
                    open(self._config['includes']['commands_path']))
            except KeyError as e:
                logging.error('Missing parameter: {0}'.format(e))
                raise Exception('Configuration file missing parameters.')

        with open(self._config['includes']['queries'][self._config['database']['queries']], 'r') as qfile:
            self._config['queries'] = yaml.safe_load(qfile)

    def get(self, arg, default=None):
        return self._config.get(arg, default)

    def __getitem__(self, arg):
        return self._config[arg]

config = Config()
