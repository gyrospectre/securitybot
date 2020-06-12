'''
The internals of securitybot. Defines a core class SecurityBot that manages
most of the bot's behavior.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import logging
import pytz
import shlex
import time

from datetime import datetime, timedelta
from re import sub

from securitybot import loader

from securitybot.user import User

from securitybot.blacklist import Blacklist

from securitybot.exceptions import SecretsException

import securitybot.commands as bot_commands


DEFAULT_COMMAND = {
    'fn': lambda b, u, a: logging.warn(
        'No function provided for this command.'
    ),
    'info': 'I was too lazy to provide information for this command',
    'hidden': False,
    'usage': None,
    'success_msg': None,
    'failure_msg': None,
}


def clean_input(text):
    '''
    Cleans some input text, doing things such as removing smart quotes.
    '''
    # Replaces smart quotes; Shlex crashes if it encounters an unbalanced
    # smart quote, as happens with auto-formatting.
    text = (text.replace(u'\u2018', '\'')
                .replace(u'\u2019', '\'')
                .replace(u'\u201c', '"')
                .replace(u'\u201d', '"'))
    # Undo autoformatting of dashes
    text = (text.replace(u'\u2013', '--')
                .replace(u'\u2014', '--'))

    return text


PUNCTUATION = r'[.,!?\'"`]'


def clean_command(command):
    # type: (str) -> str
    '''Cleans a command.'''
    command = command.lower()
    # Remove punctuation people are likely to use and
    # won't interfere with command names
    command = sub(PUNCTUATION, '', command)
    return command


class SecurityBot(object):
    '''
    It's always dangerous naming classes the same name as the project...
    '''

    def __init__(self, config):
        '''
        Args:
            chat (ChatClient):
                The type of chat client to use for messaging.
            tasker (Tasker):
                The Tasker object to get tasks from.
            auth (AuthClient):
                The type of auth client to use for MFA.
            reporting_channel (str):
                Channel ID to report alerts in need of verification to.
            config_path (str):
                Path to configuration file
        '''
        logging.info('Creating securitybot.')
        self._last_task_poll = datetime.min.replace(tzinfo=pytz.utc)
        self._last_report = datetime.min.replace(tzinfo=pytz.utc)
        self._task_poll_time = timedelta(
            seconds=int(config['bot']['timers']['task_poll_time'])
        )
        self._opening_time = config['bot']['time']['opening_hour']
        self._closing_time = config['bot']['time']['closing_hour']
        self._local_tz = pytz.timezone(config['bot']['time']['local_tz'])
        self._escalation_time_mins = (
            config['bot']['time']['escalation_time_mins']
        )
        self._backoff_time_hrs = config['bot']['time']['backoff_time_hrs']

        self._config = config

        # Load our secrets from the chosen secrets manager
        self._init_secrets()

        # Connect to the chosen auth/db/chat providers
        self._init_providers()

        self.tasker = loader.build_tasker(self._dbclient)

        self._import_commands(
            config=loader.load_yaml(
                config['bot']['commands_path']
            )
        )
        self.messages = loader.load_yaml(
            config['bot']['messages_path']
        )

        # Load blacklist from DB
        self.blacklist = Blacklist(self._dbclient)

        # A dictionary to be populated with all members of the team
        self.users = {}
        self.users_by_name = {}
        self._populate_users()

        # Dictionary of users who have outstanding tasks
        self.active_users = {}

        # Recover tasks
        self.recover_in_progress_tasks()

        logging.info('Done!')

    def _init_secrets(self):
        # Load our secrets
        secrets_provider = self._config['secretsmgmt']['provider']

        self._secretsclient = loader.build_secrets_client(
            secrets_provider=secrets_provider,
            connection_config=self._config['secretsmgmt'][secrets_provider]
        )
        try:
            loader.add_secrets_to_config(
                smclient=self._secretsclient,
                secrets=self._config['secretsmgmt']['secrets'],
                config=self._config
            )
        except Exception as error:
            raise SecretsException(
                'Failed to load secrets! {}'.format(error)
            )

    def _init_providers(self):
        auth_provider = self._config['auth']['provider']
        db_provider = self._config['database']['provider']
        chat_provider = self._config['chat']['provider']

        self._dbclient = loader.build_db_client(
            db_provider=db_provider,
            connection_config=self._config['database'][db_provider]
        )
        self._authclient = loader.build_auth_client(
            auth_provider=auth_provider,
            connection_config=self._config['auth'][auth_provider],
            reauth_time=self._config['auth']['reauth_time'],
            auth_attrib=self._config['auth']['auth_attrib']
        )
        self._chatclient = loader.build_chat_client(
            chat_provider=chat_provider,
            connection_config=self._config['chat'][chat_provider]
        )

    def _import_commands(self, config) -> None:
        '''
        Imports commands from a configuration blob.
        '''
        self.commands = {}
        for name, cmd in config.items():
            new_cmd = DEFAULT_COMMAND.copy()
            new_cmd.update(cmd)

            try:
                new_cmd['fn'] = getattr(bot_commands, format(cmd['fn']))
            except AttributeError as e:
                raise SecurityBotException('Invalid function: {0}'.format(e))

            self.commands[name] = new_cmd
        logging.info('Loaded commands: {0}'.format(self.commands.keys()))

    # Bot functions

    def run(self):
        # type: () -> None
        '''
        Main loop for the bot.
        '''
        while True:
            now = datetime.now(tz=pytz.utc)
            if now - self._last_task_poll > self._task_poll_time:
                self._last_task_poll = now
                self.handle_new_tasks()
                self.handle_in_progress_tasks()
                self.handle_verifying_tasks()
            self.handle_messages()
            self.handle_users()
            time.sleep(.1)

    def handle_messages(self):
        # type: () -> None
        '''
        Handles all messages sent to securitybot.
        Currently only active users are considered, i.e. we don't
        care if a user sends us a message but we haven't sent them anything.
        '''
        messages = self._chatclient.get_messages()
        for message in messages:
            user_id = message['user']
            text = message['text']
            user = self.user_lookup(user_id)

            # Parse each received line as a command, otherwise
            # send an error message
            if self.is_command(text):
                self.handle_command(user, text)
            else:
                self._chatclient.message_user(
                    user,
                    self.messages['bad_command']
                )

    def handle_command(self, user, command):
        # type: (User, str) -> None
        '''
        Handles a given command from a user.
        '''
        key, args = self.parse_command(command)
        logging.info('Handling command {0} for {1}'.format(key, user['name']))
        cmd = self.commands[key]
        if cmd['fn'](self, user, args):
            if cmd['success_msg']:
                self._chatclient.message_user(user, cmd['success_msg'])
        else:
            if cmd['failure_msg']:
                self._chatclient.message_user(user, cmd['failure_msg'])

    def valid_user(self, username):
        # type: (str) -> bool
        '''
        Validates a username to be valid.
        '''
        if len(username.split()) != 1:
            return False
        try:
            self.user_lookup_by_name(username)
            return True
        except SecurityBotException as e:
            logging.warn('{}'.format(e))
            return False

    def _add_task(self, task):
        '''
        Adds a new task to the user specified by that task.

        Args:
            task (Task): the task to add.
        '''
        username = task.username
        if self.valid_user(username):
            # Ignore blacklisted users
            if self.blacklist.is_present(username):
                logging.info(
                    'Ignoring task for blacklisted {0}'.format(username)
                )
                task.comment = 'blacklisted'
                task.set_verifying()
            else:
                user = self.user_lookup_by_name(username)
                user_id = user['id']
                if user_id not in self.active_users:
                    logging.debug('Adding {} to active users'.format(username))
                    self.active_users[user_id] = user

                user.add_task(task)
                task.set_in_progress()
        else:
            # Escalate if no valid user is found
            logging.warn('Invalid user: {0}'.format(username))
            task.comment = 'invalid user'
            task.set_verifying()

    def handle_new_tasks(self):
        # type: () -> None
        '''
        Handles all new tasks.
        '''
        for task in self.tasker.get_new_tasks():
            # Log new task
            logging.info('Handling new task for {0}'.format(task.username))

            self._add_task(task)

    def handle_in_progress_tasks(self):
        # type: () -> None
        '''
        Handles all in progress tasks.
        '''
        pass

    def recover_in_progress_tasks(self):
        # type: () -> None
        '''
        Recovers in progress tasks from a previous run.
        '''
        for task in self.tasker.get_active_tasks():
            # Log new task
            logging.info('Recovering task for {0}'.format(task.username))

            self._add_task(task)

    def handle_verifying_tasks(self):
        # type: () -> None
        '''
        Handles all tasks which are currently waiting for verification.
        '''
        pass

    def handle_users(self):
        # type: () -> None
        '''
        Handles all users.
        '''
        for user_id in self.active_users.copy().keys():
            user = self.active_users[user_id]
            user.step()

    def cleanup_user(self, user):
        # type: (User) -> None
        '''
        Cleanup a user from the active users list once they have no remaining
        tasks.
        '''
        logging.debug('Removing {} from active users'.format(user['name']))
        self.active_users.pop(user['id'], None)

    def alert_user(self, user, task):
        '''
        Alerts a user about an alert that was trigged and associated with their
        name.

        Args:
            user (User): The user associated with the task.
            task (Task): A task to alert on.
        '''
        self.greet_user(user)

        # Format the reason to be indented
        reason = '\n'.join(['>' + s for s in task.reason.split('\n')])

        message = self.messages['alert'].format(task.description, reason)
        message += '\n'
        message += self.messages['action_prompt']
        self._chatclient.message_user(user, message)

    # User creation and lookup methods

    def _populate_users(self):
        # type: () -> None
        '''
        Populates the members dictionary mapping user IDs to username, avatar,
        etc.
        '''
        logging.info('Gathering information about all team members...')
        members = self._chatclient.get_users()
        for member in members:
            user = User(
                user=member,
                auth=self._authclient,
                dbclient=self._dbclient,
                parent=self
            )
            self.users[member['id']] = user
            self.users_by_name[member['name']] = user
        logging.info('Gathered info on {} users.'.format(len(self.users)))

    def user_lookup(self, id):
        # type: (str) -> User
        '''
        Looks up a user by their ID.

        Args:
            id (str): The ID of a user to look up, formatted like U12345678.
        Returns:
            (dict): All known information about that user.
        '''
        if id not in self.users:
            raise SecurityBotException('User {} not found'.format(id))
        return self.users[id]

    def user_lookup_by_name(self, username):
        # type: (str) -> User
        '''
        Looks up a user by their username.

        Args:
            username (str): The username of the user to look up.
        Resturns:
            (dict): All known information about that user.
        '''
        if username not in self.users_by_name:
            raise SecurityBotException('User {} not found'.format(username))
        return self.users_by_name[username]

    # Chat methods

    def greet_user(self, user):
        # type: (User) -> None
        '''
        Sends a greeting message to a user.

        Args:
            user (User): The user to greet.
        '''
        self._chatclient.message_user(
            user,
            self.messages['greeting'].format(
                user.get_name()
            )
        )

    # Command functions
    def is_command(self, command):
        # type: (str) -> bool
        '''Checks if a raw command is a command.'''
        return clean_command(command.split()[0]) in self.commands

    def parse_command(self, command):
        '''
        Parses a given command.

        Args:
            command (str): The raw command to parse.
        Returns:
            (str, List[str]): A tuple of the command followed by arguments.
        '''
        # First try shlex
        command = clean_input(command)
        try:
            split = shlex.split(command)
        except ValueError:
            # ignore shlex exception
            # Fall back to naive method
            split = command.split()

        return (clean_command(split[0]), split[1:])


class SecurityBotException(Exception):
    pass
