import unittest

from unittest.mock import MagicMock
from unittest.mock import patch

from securitybot.db.awssimpledb import DbClient

from securitybot.exceptions import DbException


SDB_CFG = {
    'domain_prefix': 'secbot'
}


class TestChatProviderSlack(unittest.TestCase):
    @patch('securitybot.db.awssimpledb.client')
    def test__connect(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")

        self.assertEqual(cli._domain_prefix, 'secbot')
        self.assertEqual(cli.queries, '')

    @patch('securitybot.db.awssimpledb.client')
    def test__execute_unknown_query(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")

        with self.assertRaises(DbException):
            cli.execute('', params=None) 

    @patch('securitybot.db.awssimpledb.client')
    def test__execute_no_params(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")

        cli._update_ignored_list = MagicMock() 
        cli.execute('update_ignored_list', params=None)

        cli._update_ignored_list.assert_called_once_with(params=())


    @patch('securitybot.db.awssimpledb.client')
    def test__execute_update_ignored_success(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")
        cli._delete = MagicMock()
        cli._delete.return_value = True
        cli._dict_to_items = MagicMock()
        cli._dict_to_items.return_value = (['eee'], [])

        e_result = cli.execute('update_ignored_list', params=None)

        self.assertEqual(e_result, True)

    @patch('securitybot.db.awssimpledb.client')
    def test__set_response_success(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")

        params = ('comment', 0, 0, 'hash')
        e_result = cli.execute('set_response', params=params)

        cli._new_alert_user_response = MagicMock()
        self.assertEqual(e_result, True)

    @patch('securitybot.db.awssimpledb.client')
    def test__set_response_success_pop(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")

        params = ('comment', 0, 0, 'hash')
        cli._new_alert_user_response = MagicMock()
        cli.execute('set_response', params=params)

        cli._new_alert_user_response.assert_called_once_with(['hash', 'comment', 0, 0])

    @patch('securitybot.db.awssimpledb.client')
    def test__set_response_params_missing(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")

        with self.assertRaises(DbException):
            cli.execute('set_response')

    @patch('securitybot.db.awssimpledb.client')
    def test__get_alerts_no_params(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries="test")

        with self.assertRaises(DbException):
            cli.execute('get_alerts')

    @patch('securitybot.db.awssimpledb.client')
    def test__get_alerts_success(self, mk_boto):
        cli = DbClient(config=SDB_CFG, queries=None)
        cli._select = MagicMock()
        cli._select.return_value = {
            'ee': {
                'title': 'test',
                'ldap': 'user',
                'reason': 'because',
                'description': 'hi',
                'url': 'n/a',
                'event_time': '2020-01-01T00:00:00+0000',
                'performed': 0,
                'comment': 'woot',
                'authenticated': 0,
                'status': 2
            }
        }

        cli.execute('get_alerts', params = ('0'))
