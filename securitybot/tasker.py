'''
A system for retrieving and assigning tasks for the bot as well as updating
their statuses once acted up. This file contains two abstract classes,
Tasker and Task, which define a class to manage tasks and a task class
respectively.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import pytz
import logging

from enum import Enum, unique

from typing import List


@unique
class StatusLevel(Enum):
    # Task status levels
    OPEN = 0            # New task
    INPROGRESS = 1      # User has been told
    VERIFICATION = 2    # User has said it was them, we're verifying
    DONE = 3            # User has said they didn't do it, they didn't
                        # respond at all, or they said yes and we verified


class Task(object):

    def __init__(self, hsh, title, username, reason, description,
                 url, event_time, performed, comment, authenticated,
                 status, dbclient):
        # type: (str, str, str, str, str, bool, str, bool, int) -> None
        '''
        Creates a new Task for an alert that should go to `username` and is
        currently set to `status`.

        Args:
            title (str): The title of this task.
            username (str): The user who should be alerted from the Task.
            reason (str): The reason that the alert was fired.
            description (str): A description of the alert in question.
            url (str): A URL in which more information can be found about the
                       alert itself, not the Task.
            performed (bool): Whether or not the user performed the action that
                              caused this alert.
            comment (str): The user's comment on why the action occured.
            authenticated (bool): Whether 2FA has suceeded.
            status (enum): See `STATUS_LEVELS` from above.
        '''
        self.title = title
        self.username = username
        self.reason = reason
        self.description = description
        self.url = url
        self.event_time = event_time.astimezone(pytz.UTC)
        self.performed = performed
        self.comment = comment
        self.authenticated = authenticated
        self.status = status
        self._dbclient = dbclient
        self.hash = hsh

    def _set_status(self, status):
        # type: (int) -> None
        '''
        Sets the status of a task in the DB.

        Args:
            status (int): The new status to use.
        '''
        self._dbclient.execute('set_status', (status, self.hash))

    def _set_response(self):
        # type: () -> None
        '''
        Updates the user response for this task.
        '''
        self._dbclient.execute(
            'set_response',
            (
                self.comment,
                self.performed,
                self.authenticated,
                self.hash
            )
        )

    def set_open(self):
        self._set_status(StatusLevel.OPEN.value)

    def set_in_progress(self):
        self._set_status(StatusLevel.INPROGRESS.value)

    def set_verifying(self):
        self._set_status(StatusLevel.VERIFICATION.value)
        self._set_response()

    def finalise(self):
        self._set_status(StatusLevel.DONE.value)
        logging.debug('Deleting task {} from database.'.format(
            self.hash)
        )
        self._dbclient.execute(
            'delete_alert', (self.hash, )
        )
        self._dbclient.execute(
            'delete_alert_status', (self.hash, )
        )
        self._dbclient.execute(
            'delete_user_response', (self.hash, )
        )

class Tasker(object):
    '''
    A simple class to retrieve tasks on which the bot should act upon.
    '''

    def __init__(self, dbclient):
        self._dbclient = dbclient

    def _get_tasks(self, level) -> List[Task]:
        # type: (int) -> List[Task]
        '''
        Gets all tasks of a certain level.

        Args:
            level (int): One of StatusLevel
        Returns:
            List of SQLTasks.
        '''
        alerts = self._dbclient.execute('get_alerts', (level,))
        return [Task(*alert, dbclient=self._dbclient) for alert in alerts]

    def get_new_tasks(self):
        # type: () -> List[Task]
        return self._get_tasks(StatusLevel.OPEN.value)

    def get_active_tasks(self):
        # type: () -> List[Task]
        return self._get_tasks(StatusLevel.INPROGRESS.value)

    def get_pending_tasks(self):
        # type: () -> List[Task]
        return self._get_tasks(StatusLevel.VERIFICATION.value)

