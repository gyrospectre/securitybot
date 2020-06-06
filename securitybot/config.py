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

    def get(self, arg, default=None):
        return self._config.get(arg, default)

    def __getitem__(self, arg):
        return self._config[arg]
