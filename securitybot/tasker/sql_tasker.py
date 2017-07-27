'''
A tasker on top of a SQL database.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

from securitybot.tasker.tasker import Task, Tasker, StatusLevel
from securitybot.db.engine import DbEngine

from typing import List

# Note: this order is provided to match the SQLTask constructor
GET_ALERTS = '''
SELECT HEX(alerts.hash),
       title,
       ldap,
       reason,
       description,
       url,
       performed,
       comment,
       authenticated,
       status
FROM alerts
JOIN user_responses ON alerts.hash = user_responses.hash
JOIN alert_status ON alerts.hash = alert_status.hash
WHERE status = %s
'''


class SQLTasker(Tasker):

    def __init__(self):
        self._db_engine = DbEngine()

    def _get_tasks(self, level) -> List[Task]:
        # type: (int) -> List[Task]
        '''
        Gets all tasks of a certain level.

        Args:
            level (int): One of StatusLevel
        Returns:
            List of SQLTasks.
        '''
        alerts = self._db_engine.execute(GET_ALERTS, (level,))
        return [SQLTask(*alert) for alert in alerts]

    def get_new_tasks(self):
        # type: () -> List[Task]
        return self._get_tasks(StatusLevel.OPEN.value)

    def get_active_tasks(self):
        # type: () -> List[Task]
        return self._get_tasks(StatusLevel.INPROGRESS.value)

    def get_pending_tasks(self):
        # type: () -> List[Task]
        return self._get_tasks(StatusLevel.VERIFICATION.value)

SET_STATUS = '''
UPDATE alert_status
SET status=%s
WHERE hash=UNHEX(%s)
'''

SET_RESPONSE = '''
UPDATE user_responses
SET comment=%s,
    performed=%s,
    authenticated=%s
WHERE hash=UNHEX(%s)
'''


class SQLTask(Task):

    def __init__(self, hsh, title, username, reason, description, url,
                 performed, comment, authenticated, status):
        # type: (str, str, str, str, str, str, bool, str, bool, int) -> None
        '''
        Args:
            hsh (str): SHA256 primary key hash.
        '''
        super(SQLTask, self).__init__(title, username, reason, description, url,
                                      performed, comment, authenticated, status)
        self.hash = hsh

    def _set_status(self, status):
        # type: (int) -> None
        '''
        Sets the status of a task in the DB.

        Args:
            status (int): The new status to use.
        '''
        self._db_engine.execute(SET_STATUS, (status, self.hash))

    def _set_response(self):
        # type: () -> None
        '''
        Updates the user response for this task.
        '''
        self._db_engine.execute(SET_RESPONSE, (self.comment,
                                               self.performed,
                                               self.authenticated,
                                               self.hash))

    def set_open(self):
        self._set_status(StatusLevel.OPEN.value)

    def set_in_progress(self):
        self._set_status(StatusLevel.INPROGRESS.value)

    def set_verifying(self):
        self._set_status(StatusLevel.VERIFICATION.value)
        self._set_response()
