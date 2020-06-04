'''
A wrapper over the Slack API.
'''
__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import logging
import asyncio
import ssl as ssl_lib
import certifi
import threading

from slack import WebClient
from slack import RTMClient

from typing import Any, Dict, List

from securitybot.user import User

from securitybot.chat.chat import BaseChatClient, ChatException

class ChatClient(BaseChatClient):
    '''
    A wrapper around the Slack API designed for Securitybot.
    '''
    # username: str, token: str, icon_url: str=None) -> None:
    def __init__(self, connection_config) -> None:
        '''
        Constructs the Slack API object using the bot's username, a Slack
        token, and a URL to what the bot's profile pic should be.
        '''
        self._username = connection_config['username']
        self._icon_url = connection_config['icon_url']
        self.reporting_channel = connection_config['reporting_channel']
        self.messages = []
        self._token = connection_config['token']
        
        self._slack_web = WebClient(self._token)
        self._validate()

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=self.connect, args=(loop,))
        thread.start() 

    def _validate(self) -> None:
        '''Validates Slack API connection.'''
        response = self._slack_web.api_test()
        if not response['ok']:
            raise ChatException('Unable to connect to Slack API.')
        logging.info('Connection to Slack API successful!')

    def connect(self, loop):
        asyncio.set_event_loop(loop)
        ssl_context = ssl_lib.create_default_context(cafile=certifi.where())

        self._slack_rtm = RTMClient(
            token=self._token,
            ssl=ssl_context,
            run_async=True,
            loop=loop
        )
        #loop.run_forever(
        #    self._slack_rtm.start()
        #)
        self._slack_rtm.run_on(event="message")(self.get_message)
        loop.run_until_complete(
            self._slack_rtm.start()
        )

    def get_users(self) -> List[Dict[str, Any]]:
        '''
        Returns a list of all users in the chat system.

        Returns:
            A list of dictionaries, each dictionary representing a user.
            The rest of the bot expects the following minimal format:
            {
                "name": The username of a user,
                "id": A user's unique ID in the chat system,
                "profile": A dictionary representing a user with at least:
                    {
                        "first_name": A user's first name
                    }
            }
        '''
        return self._slack_web.users_list()['members']

    def get_messages(self):
        messages = self.messages
        self.messages = []

        return messages

    async def get_message(self, **payload):
        '''
        Gets a list of all new messages received by the bot in direct
        messaging channels. That is, this function ignores all messages
        posted in group chats as the bot never interacts with those.

        Each message should have the following format, minimally:
        {
            "user": The unique ID of the user who sent a message.
            "text": The text of the received message.
        }
        '''
        data = payload["data"]
        if 'user' in data and data['channel'].startswith('D'):
            message = {}
            message['user'] = data['user']
            message['text'] = data['text']
            self.messages.append(message)

    def send_message(self, channel: Any, message: str) -> None:
        '''
        Sends some message to a desired channel.
        As channels are possibly chat-system specific, this function has a horrible
        type signature.
        '''
        self._slack_web.chat_postMessage(
            channel=channel,
            text=message,
            username=self._username,
            as_user=False,
            icon_url=self._icon_url
        )

    def message_user(self, user: User, message: str=None):
        '''
        Sends some message to a desired user, using a User object and a string message.
        '''
        channel = self._slack_web.im_open(user=user['id'])['channel']['id']
        self.send_message(channel, message)
