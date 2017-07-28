'''
A small file for keeping track of ignored alerts in the database.
'''
import pytz
from datetime import timedelta, datetime
from typing import Dict

from securitybot.db.engine import DbEngine
from securitybot.config import config


def __update_ignored_list() -> None:
    # type: () -> None
    '''
    Prunes the ignored table of old ignored alerts.
    '''
    if config['queries'].get('update_ignored_list', False):
        DbEngine().execute(config['queries']['update_ignored_list'])


def get_ignored(username: str) -> Dict[str, str]:
    '''
    Returns a dictionary of ignored alerts to reasons why
    the ignored are ignored.

    Args:
        username (str): The username of the user to retrieve ignored alerts for.
    Returns:
        Dict[str, str]: A mapping of ignored alert titles to reasons
    '''
    __update_ignored_list()
    rows = DbEngine().execute(config['queries']['get_ignored'], (username,))
    return {row[0]: row[1] for row in rows}


def ignore_task(username: str, title: str, reason: str, ttl: timedelta) -> None:
    '''
    Adds a task with the given title to the ignore list for the given
    amount of time. Additionally adds an optional message to specify the
    reason that the alert was ignored.

    Args:
        username (str): The username of the user to ignore the given alert for.
        title (str): The title of the alert to ignore.
        ttl (Timedelta): The amount of time to ignore the alert for.
        msg (str): An optional string specifying why an alert was ignored
    '''
    expiry_time = datetime.now(tz=pytz.utc) + ttl
    # NB: Non-standard MySQL specific query
    DbEngine().execute(config['queries']['ignore_task'],
                       (username, title, reason, expiry_time.strftime('%Y-%m-%d %H:%M:%S')))
