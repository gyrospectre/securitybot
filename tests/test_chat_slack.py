import unittest
import json

from unittest.mock import MagicMock
from unittest.mock import patch

from securitybot.chat.slack import ChatClient

from securitybot.exceptions import ChatException


SLACK_CFG = {
    'username': 'CyberBot',
    'reporting_channel': 'Cxxxxxxxxxx',
    'icon_url': 'http://test.com/1.png',
    'token': '1234'
}

class TestChatProviderSlack(unittest.TestCase):
    @patch('securitybot.chat.slack.RTMClient')
    @patch('securitybot.chat.slack.WebClient')
    def test__connect(self, mk_web, mk_rtm):
        ChatClient.connect = MagicMock()
        ChatClient(connection_config=SLACK_CFG)

        mk_web.assert_called_once_with('1234')

    @patch('securitybot.chat.slack.RTMClient')
    @patch('securitybot.chat.slack.WebClient')
    def test__message_user(self, mk_web, mk_rtm):
        ChatClient.connect = MagicMock()
        cli = ChatClient(connection_config=SLACK_CFG)

        cli._slack_web.im_open.return_value = {'channel': {'id': '11'} }
        cli.message_user(user={'id': 'test'}, message='what?')

        cli._slack_web.chat_postMessage.assert_called_once_with(
            as_user=False,
            channel='11',
            icon_url='http://test.com/1.png',
            text='what?',
            username='CyberBot'
        )

    @patch('securitybot.chat.slack.RTMClient')
    @patch('securitybot.chat.slack.WebClient')
    def test__validate_fail(self, mk_web, mk_rtm):
        cli = ChatClient(connection_config=SLACK_CFG)

        cli._slack_web.api_test.return_value = {'ok': False}

        with self.assertRaises(ChatException):
            cli._validate()

    @patch('securitybot.chat.slack.RTMClient')
    @patch('securitybot.chat.slack.WebClient')
    def test__get_users(self, mk_web, mk_rtm):
        cli = ChatClient(connection_config=SLACK_CFG)

        users = ['bill', 'sally']
        cli._slack_web.users_list.return_value = {'members': users}
        u_result = cli.get_users()
        

        self.assertEqual(u_result, (users))
