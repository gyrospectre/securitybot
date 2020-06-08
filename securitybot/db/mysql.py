'''
A wrapper for the securitybot to access its database.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import MySQLdb
import logging
from typing import Any, Dict, Sequence

from securitybot.db.database import BaseDbClient

from securitybot.exceptions import DbException


class DbClient(BaseDbClient):

    def __init__(self, config: Dict[str, Any], queries):
        '''
        Initializes the SQL connection to be used for the bot.

        Args:
            config (Dict): Configuration for this engine.
        '''
        self._host = config.get('host', None)
        self._user = config.get('user', None)
        self._passwd = config.get('password', None)
        self._db = config.get('db', None)
        self._create_engine()
        self.queries = queries

    def _create_engine(self):
        # type: (str, str, str, str) -> None
        '''
        Args:
            host (str): The hostname of the SQL server.
            user (str): The username to use.
            passwd (str): Password for MySQL user.
            db (str): The name of the database to connect to.
        '''
        self._conn = MySQLdb.connect(host=self._host,
                                     user=self._user,
                                     passwd=self._passwd,
                                     db=self._db)
        self._cursor = self._conn.cursor()

    def execute(self, query_ref: str, params: Sequence=None):
        # type: (str, Sequence[Any]) -> Sequence[Sequence[Any]]
        '''
        Executes a given SQL query with some possible params.

        Args:
            query (str): The query to perform.
            params (Tuple[str]): Optional parameters to pass to the query.
        Returns:
            Tuple[Tuple[str]]: The output from the SQL query.
        '''
        query = self.queries[query_ref]
        if params is None:
            params = ()
        try:
            logging.debug('Executing: ' + query + str(params))
            self._cursor.execute(query, params)
            rows = self._cursor.fetchall()
            self._conn.commit()
        except (AttributeError, MySQLdb.OperationalError):
            # Recover from lost connection
            logging.warn('Recovering from lost MySQL connection.')
            self._create_engine()
            return self.execute(query, params)
        except MySQLdb.Error as e:
            try:
                raise SQLEngineException('MySQL error [{0}]: {1}'.format(e.args[0], e.args[1]))
            except IndexError:
                raise SQLEngineException('MySQL error: {0}'.format(e))
        logging.debug('Result: ' + str(rows))
        return rows


class SQLEngineException(DbException):
    pass
