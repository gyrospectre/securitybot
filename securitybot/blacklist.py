'''
A generic blacklist class.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'


class Blacklist(object):

    def __init__(self, dbclient):
        # type: () -> None
        '''
        Creates a new blacklist tied to a table named "blacklist".
        '''
        # Load from table
        self._db_engine = dbclient
        names = self._db_engine.execute(self._db_engine.queries['blacklist_list'])
        # Break tuples into names
        self._blacklist = {name[0] for name in names}

    def is_present(self, name):
        # type: (str) -> bool
        '''
        Checks if a name is on the blacklist.

        Args:
            name (str): The name to check.
        '''
        return name in self._blacklist

    def add(self, name):
        # type: (str) -> None
        '''
        Adds a name to the blacklist.

        Args:
            name (str): The name to add to the blacklist.
        '''
        self._blacklist.add(name)
        self._db_engine.execute(config['queries']['blacklist_add'], (name,))

    def remove(self, name):
        # type: (str) -> None
        '''
        Removes a name to the blacklist.

        Args:
            name (str): The name to remove from the blacklist.
        '''
        self._blacklist.remove(name)
        self._db_engine.execute(config['queries']['blacklist_remove'], (name,))
