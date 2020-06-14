'''
A wrapper for the securitybot to access its database.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import MySQLdb
import logging

from typing import Any, Dict, Sequence

from MySQLdb._exceptions import OperationalError
from MySQLdb.constants.ER import NO_SUCH_TABLE, TABLE_EXISTS_ERROR, BAD_DB_ERROR
from MySQLdb.constants.CR import CONNECTION_ERROR

from securitybot.db.database import BaseDbClient

from securitybot.exceptions import DbException


class DbClient(BaseDbClient):

    def __init__(self, config, queries):
        '''
        Initializes the SQL connection to be used for the bot.

        Args:
            config (Dict): Configuration for this engine.
        '''
        
        self._host = config.get('host', None)
        self._user = config.get('user', None)
        self._passwd = config.get('password', None)
        self.queries = queries
        self._tables = config.get('tables', None)

        self._db = config.get('db', None)
        self._create_engine()
        self._init_tables()

    def _create_engine(self):
        # type: (str, str, str, str) -> None
        '''
        Args:
            host (str): The hostname of the SQL server.
            user (str): The username to use.
            passwd (str): Password for MySQL user.
            db (str): The name of the database to connect to.
        '''
        try:
            self._conn = MySQLdb.connect(
                host=self._host,
                user=self._user,
                passwd=self._passwd,
                db=self._db
            )
            self._cursor = self._conn.cursor()

        except OperationalError as error:
            logging.info('Database {} does not exist, creating.'.format(self._db))
            db = MySQLdb.connect(
                host=self._host,
                user=self._user,
                passwd=self._passwd
            )
            self._cursor = db.cursor()
            self._cursor.execute('CREATE DATABASE {}'.format(self._db))
            logging.info('Database created.'.format(self._db))
            self._create_engine()
            return

        logging.info('Connected to database {}.'.format(self._db))

    def _init_tables(self):
        logging.debug('Checking tables are present')
        tables = self.execute('get_tables')
        curr_list = []
        for table in tables:
            curr_list.append(table[0])

        if all(item in curr_list for item in self._tables) is not True:
            logging.info('All tables not present, creating.')
            self._create_tables(self._tables)
        
        logging.info('Tables present.')
        

    def execute(self, query_ref: str, params: Sequence = None):
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
            print(query, params)
            self._cursor.execute(query, params)
            rows = self._cursor.fetchall()
            self._conn.commit()
            logging.debug('Result: ' + str(rows))
            return rows

        except OperationalError as error:
            # Handle specific errors
            errcode = error.args[0]
            if errcode == TABLE_EXISTS_ERROR:
                # Ignore existing table error
                return []
            elif errcode == CONNECTION_ERROR:
                # Recover from lost connection
                logging.warn('Recovering from lost MySQL connection. {}'.format(error))
                self._create_engine()
                return self.execute(query, params)
            elif errcode == NO_SUCH_TABLE:
                # Somehow a table was deleted, fix and recover
                self._init_tables()
                return self.execute(query, params)
            elif errcode == BAD_DB_ERROR:
                # Ignore unknown DB, hanlded in _create_engine
                return []
            else:
                raise

        except MySQLdb.Error as e:
            try:
                if e.args[0] == TABLE_EXISTS_ERROR:
                    # Ignore existing table error
                    pass
                else:
                    raise SQLEngineException(
                        'MySQL error [{0}]: {1}'.format(e.args[0], e.args[1])
                    )
            except IndexError:
                raise SQLEngineException('MySQL1 error: {0}'.format(e))


    def _create_tables(self, tablelist):
        '''
        Create all tables in list, if they don't already exist
        '''
        for table in tablelist:
            try:
                self.execute('create_table_{}'.format(table))
            except OperationalError as error:
                logging.debug('Table {} already exists'.format(table))
                pass        
        
        return True

    def delete_table(self, table):
        '''
        Deletes a table
        '''
        try:
            query = "DROP TABLE {}".format(table)
            self._cursor.execute(query)
            rows = self._cursor.fetchall()
            self._conn.commit()

        except Exception as e:
            logging.error("Table '{}' deletion failed! ({})".format(table, e))
            return False, e
        
        return True, rows

    def dump_table(self, table):
        '''
        Dumps a table
        '''
        try:
            self._cursor.execute('SELECT * FROM {}'.format(table))
            rows = self._cursor.fetchall()
            self._conn.commit()
            return rows
        except OperationalError as error:
            logging.debug('Table {} already exists'.format(table))


class SQLEngineException(DbException):
    pass
