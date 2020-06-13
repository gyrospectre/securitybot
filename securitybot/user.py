'''
An object to manage user interactions.
Wraps user information, all known alerts, and an
active DM channel with the user.
'''
__author__ = 'Alex Bertsch'
__email__ = 'abertsch@dropbox.com'

import logging
import pytz
from datetime import datetime, timedelta

import securitybot.ignored_alerts as ignored_alerts
from securitybot.auth.auth import AuthStates
from securitybot.state_machine import StateMachine
from securitybot.util import tuple_builder, get_expiration_time


class User(object):
    '''
    A user to be contacted by the security bot. Each user stores all of the
    information provided by chat, which is indexable similar to a dictionary.
    A user also holds a reference to an authentication object for 2FA and the
    bot who spawned it for sending messages.
    '''

    def __init__(self, user, auth, dbclient, parent):
        '''
        Args:
            user (dict): Chat information about a user.
            auth (AuthClient): The authentication client to use.
            parent (Bot): The bot object that spawned this user.
        '''
        self._user = user
        self.tasks = []
        self.pending_task = None
        # Authentication object specific to this user
        self._authclient = auth
        self._dbclient = dbclient

        # Parent pointer to bot
        self._bot = parent

        # Last parsed message from this user
        self._last_message = tuple_builder()

        # Last authorization details
        self._last_auth_state = AuthStates.NONE
        self._last_auth_time = datetime.min

        # Task auto-escalation time
        self._escalation_time = datetime.max.replace(tzinfo=pytz.utc)

        # If user is enrolled in MFA
        self._can_auth = self._authclient.can_auth(self)

        # Factor to be used for MFA
        if self._can_auth is not False:
            self._factor_id = self._can_auth
            self._can_auth = True

        # Build state hierarchy
        states = ['need_task',
                  'action_performed_check',
                  'auth_permission_check',
                  'waiting_on_auth',
                  'task_finished',
                  ]
        transitions = [
            # Handle new tasks
            {
                'source': 'need_task',
                'dest': 'action_performed_check',
                'condition': self._has_tasks
            },
            # Finish task if user says action was
            # performed and recently authorized
            {
                'source': 'action_performed_check',
                'dest': 'task_finished',
                'condition': self._already_authed,
            },
            # Finish task if user says action was performed
            # and no 2FA capability exists
            {
                'source': 'action_performed_check',
                'dest': 'task_finished',
                'condition': self._cannot_2fa,
                'action': lambda: self.send_message('no_2fa')
            },
            # Ask for 2FA if user says action was performed and can do 2FA
            {
                'source': 'action_performed_check',
                'dest': 'auth_permission_check',
                'condition': self._performed_action,
            },
            # Finish task if user says action wasn't performed
            {
                'source': 'action_performed_check',
                'dest': 'task_finished',
                'condition': self._did_not_perform_action,
                'action': self._act_on_not_performed,
            },
            # Silently escalate and wait after some time goes by
            {
                'source': 'action_performed_check',
                'dest': 'task_finished',
                'condition': self._slow_response_time,
                'action': self._auto_escalate,
            },
            # Perform 2FA if permission is granted
            {
                'source': 'auth_permission_check',
                'dest': 'waiting_on_auth',
                'condition': self._allows_authorization,
            },
            # Don't perform 2FA if permission is not granted
            {
                'source': 'auth_permission_check',
                'dest': 'task_finished',
                'condition': self._denies_authorization,
                'action': self._act_on_denied_mfa
            },
            # Silently escalate and wait after some time goes by again
            {
                'source': 'auth_permission_check',
                'dest': 'task_finished',
                'condition': self._slow_response_time,
                'action': self._auto_escalate,
            },
            # Wait for authorization response then finish the task
            {
                'source': 'waiting_on_auth',
                'dest': 'task_finished',
                'condition': self._auth_completed,
            },
            # Go to the first needed task, possibly quitting,
            # when task is completed
            {
                'source': 'task_finished',
                'dest': 'need_task',
            },
        ]
        during = {
            'waiting_on_auth': self._update_auth,
        }
        on_enter = {
            'auth_permission_check': lambda: self.send_message('2fa'),
            'waiting_on_auth': lambda: self.begin_auth(),
        }
        on_exit = {
            'need_task': self._next_task,
            'action_performed_check': self._update_task_response,
            'auth_permission_check': self._reset_message,
            'waiting_on_auth': self._update_task_auth,
            'task_finished': self._complete_task,
        }

        self._fsm = StateMachine(
            states,
            transitions,
            'need_task',
            during=during,
            on_enter=on_enter,
            on_exit=on_exit
        )

    def __getitem__(self, key):
        '''
        Allows for indexing on the user infomation pulled from our chat system.
        '''
        return self._user.get(key, None)

    def step(self):
        # type: () -> None
        self._fsm.step()

    def _update_auth(self):
        # type: () -> None
        self._last_auth = self.auth_status()

    # State conditions

    def _has_tasks(self):
        # type: () -> bool
        '''Checks if the user has any tasks.'''
        return len(self.tasks) != 0

    def _already_authed(self):
        # type: () -> bool
        '''
        Checks if the user performed the last action and
        if they are already authorized.
        '''
        return (
            self._performed_action() and
            self.auth_status() == AuthStates.AUTHORIZED
        )

    def _cannot_2fa(self):
        # type: () -> bool
        return self._performed_action() and not self._can_auth

    def _performed_action(self):
        # type: () -> bool
        '''Checks if the user performed their current action.'''
        return self._last_message.answer is True

    def _did_not_perform_action(self):
        # type: () -> bool
        '''Checks if the user _did not_ perform their current action.'''
        return self._last_message.answer is False

    def _slow_response_time(self):
        # type: () -> bool
        '''Returns true if the user has taken a long time to respond.'''
        return (
            datetime.now(tz=pytz.utc) > (
                self.pending_task.event_time + timedelta(
                    minutes=self._bot._escalation_time_mins
                )
            )
        )

    def _allows_authorization(self):
        # type: () -> bool
        '''Checks if the user is okay with 2FA.'''
        return self._last_message.answer is True

    def _denies_authorization(self):
        # type: () -> bool
        '''Checks if the user is not okay with 2FA.'''
        return self._last_message.answer is False

    def _auth_completed(self):
        # type: () -> bool
        '''Checks if authentication has been completed.'''
        return (
            self._last_auth is AuthStates.AUTHORIZED or
            self._last_auth is AuthStates.DENIED
        )

    # State actions

    def _auto_escalate(self):
        # type: () -> None
        '''Marks the current task as needing verification and moves on.'''
        logging.info('Silently escalating {0} for {1}'
                     .format(self.pending_task.description, self['name']))
        # Alert bot's reporting channel
        if self._bot._chatclient.reporting_channel is not None:
            # Format message
            self._bot._chatclient.send_message(
                self._bot._chatclient.reporting_channel,
                self._bot.messages['report_noresponse'].format(
                    username=self['name'],
                    title=self.pending_task.title,
                    description=self.pending_task.description,
                    url=self.pending_task.url
                )
            )
        # Append in the case that this is called
        # when waiting for auth permission
        self.pending_task.comment += 'Auto escalated. No response received.'
        self.pending_task.set_verifying()
        self._escalation_time = datetime.max.replace(tzinfo=pytz.utc)
        self.send_message('no_response')

    def _act_on_not_performed(self):
        # type: () -> None
        '''
        Acts on a user not performing an action.
        Sends a message and alerts the bot's reporting channel.
        '''
        # Send escalation method
        self.send_message('escalated')
        # Alert bot's reporting channel
        if self._bot._chatclient.reporting_channel is not None:
            # Format message
            if self._last_message.text:
                comment = self._last_message.text
            else:
                comment = 'No comment provided.'
            comment = '\n'.join('> ' + s for s in comment.split('\n'))
            self._bot._chatclient.send_message(
                self._bot._chatclient.reporting_channel,
                self._bot.messages['report'].format(
                    username=self['name'],
                    title=self.pending_task.title,
                    description=self.pending_task.description,
                    comment=comment,
                    url=self.pending_task.url
                )
            )

    def _act_on_denied_mfa(self):
        # type: () -> None
        '''
        Acts on a user not ok with an MFA.
        Sends a message and alerts the bot's reporting channel.
        '''
        # Send escalation method
        self.send_message('escalated')
        # Alert bot's reporting channel
        if self._bot._chatclient.reporting_channel is not None:
            # Format message
            comment = 'User not comfortable performing MFA check.'
            comment = '\n'.join('> ' + s for s in comment.split('\n'))
            self._bot._chatclient.send_message(
                self._bot._chatclient.reporting_channel,
                self._bot.messages['report'].format(
                    username=self['name'],
                    title=self.pending_task.title,
                    description=self.pending_task.description,
                    comment=comment,
                    url=self.pending_task.url
                )
            )

    # Exit actions

    def _update_task_response(self):
        # type: () -> None
        '''
        Updates the task with information gained from the user's response.
        '''
        if self._last_message.answer is not None:
            self.pending_task.performed = self._last_message.answer
            self.pending_task.comment = self._last_message.text

        self._reset_message()

    def _update_task_auth(self):
        # type: () -> None
        '''
        Updates the task with authorization permission.
        '''
        if self._last_auth is AuthStates.AUTHORIZED:
            self.send_message('good_auth')
            self.pending_task.authenticated = True
        else:
            self.send_message('bad_auth')
            self.reset_auth()
            self.pending_task.authenticated = False

    def _reset_message(self):
        # type: () -> None
        self._last_message = tuple_builder()

    # Task methods

    def add_task(self, task):
        '''
        Adds a task to this user's new tasks.

        Args:
            task (Task): The Task to add.
        '''
        self.tasks.append(task)
        self._update_tasks()

    def _next_task(self):
        # type: () -> None
        '''
        Advances to the next task if there is no pending task and alerts the
        user of its existence.
        '''
        self.pending_task = self.tasks.pop(0)
        self._bot.alert_user(self, self.pending_task)
        self._reset_message()
        self._escalation_time = get_expiration_time(
            start=datetime.now(tz=pytz.utc),
            ttl=timedelta(minutes=self._bot._escalation_time_mins),
            bot=self._bot
        )
        logging.info('Beginning task for {0}'.format(self['name']))

    def _complete_task(self):
        # type: () -> None
        '''
        Completes the user's pending task. If any remaining tasks exist, sends
        a message alerting the user of more. Otherwise sends a farewell message
        and removes itself from the bot.
        '''
        print("here ################################################################################### {}".format(self.pending_task))
        # Ignore an alert if they did it
        if self.pending_task.performed:
            ignored_alerts.ignore_task(
                dbclient=self._dbclient,
                username=self['name'],
                title=self.pending_task.title,
                reason='auto backoff after confirmation',
                ttl=timedelta(hours=self._bot._backoff_time_hrs)
            )
        self.pending_task.finalise()
        self.pending_task = None
        self._reset_message()
        self._update_tasks()
        if self.tasks:
            self.send_message('bwtm')
        else:
            self.send_message('bye')
            self._bot.cleanup_user(self)

    def _update_tasks(self):
        # type: () -> None
        '''
        Updates the user's stored list of tasks, removing
        all of those that should be ignored.
        '''
        ignored = ignored_alerts.get_ignored(self._dbclient, self['name'])
        cleaned_tasks = []
        for task in self.tasks:
            if task.title in ignored:
                logging.info(
                    'Ignoring task {0} for {1}'.format(
                        task.title,
                        self['name']
                    )
                )
                task.comment = ignored[task.title]
                task.set_verifying()
            else:
                cleaned_tasks.append(task)
        self.tasks = cleaned_tasks

    # Message methods

    def positive_response(self, text):
        # type: (str) -> None
        '''
        Registers a positive response having been received.

        Args:
            text (str): Some message accompanying the response.
        '''
        self._last_message = tuple_builder(True, text)

    def negative_response(self, text):
        # type: (str) -> None
        '''
        Registers a negative response having been received.

        Args:
            text (str): Some message accompanying the response.
        '''
        self._last_message = tuple_builder(False, text)

    def send_message(self, key):
        # type: (str) -> None
        '''
        Sends a message from the pre-loaded messages.yaml.

        Args:
            key (str): The key in messages.yaml of the message to send.
        '''
        self._bot._chatclient.message_user(self, self._bot.messages[key])

    # Authorization methods

    def begin_auth(self):
        # type: () -> None
        '''
        Attempts to authorize this user. Changes the user's state to
        WAITING_ON_AUTH.
        '''
        self.send_message('sending_push')
        self._authclient.auth(self, self.pending_task.description)

    def auth_status(self):
        # type: () -> int
        '''
        Gets the current authorization status for this user.
        '''
        return self._authclient.auth_status(self)

    def reset_auth(self):
        # type: () -> None
        '''
        Resets this user's authorization status, including no longer accepting
        authorization due to being "recently" authorized.
        '''
        self._authclient.reset(self)

    # Utility methods

    def get_name(self):
        # type: () -> str
        '''
        Tries to find the best name to use when talking to a user.
        '''
        if ('profile' in self._user and
                'first_name' in self._user['profile'] and
                self._user['profile']['first_name']):
            return self._user['profile']['first_name']
        return self._user['name']

    def get_email(self):
        if ('profile' in self._user and
                'email' in self._user['profile'] and
                self._user['profile']['email']):
            return self._user['profile']['email']
        return False

    def get_displayname(self):
        if ('profile' in self._user and
                'email' in self._user['profile'] and
                self._user['profile']['display_name']):
            return self._user['profile']['display_name']
        return False


class UserException(Exception):
    pass
