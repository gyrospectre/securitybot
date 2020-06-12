__author__ = 'Alex Bertsch, Antoine Cardon'
__email__ = 'abertsch@dropbox.com, antoine.cardon@algolia.com'

import pytz
import binascii
import os
from datetime import datetime, timedelta
from collections import namedtuple

from securitybot.tasker import StatusLevel


def tuple_builder(answer=None, text=None):
    tup = namedtuple('Response', ['answer', 'text'])
    tup.answer = answer if answer is not None else None
    tup.text = text if text is not None else ''
    return tup


def during_business_hours(time, bot):
    '''
    Checks if a given time is within business hours. Currently is true
    from 10:00 to 17:59. Also checks to make sure that the day is a weekday.

    Args:
        time (Datetime): A datetime object to check.
    '''
    if time.tzinfo is not None:
        here = time.astimezone(bot._local_tz)
    else:
        here = time.replace(tzinfo=pytz.utc).astimezone(bot._local_tz)
    return (bot._opening_time <= here.hour < bot._closing_time and
            1 <= time.isoweekday() <= 5)


def get_expiration_time(start, ttl, bot):
    '''
    Gets an expiration time for an alert.
    Works by adding on a certain time and wrapping around after business hours
    so that alerts that are started near the end of the day don't expire.

    Args:
        start (Datetime):
            A datetime object indicating when an alert was started.
        ttl (Timedelta):
            A timedelta representing the amount of time the alert
            should live for.
    Returns:
        Datetime: The expiry time for an alert.
    '''
    if start.tzinfo is None:
        start = start.replace(tzinfo=pytz.utc)
    end = start + ttl
    if not during_business_hours(end, bot):
        end_of_day = datetime(year=start.year,
                              month=start.month,
                              day=start.day,
                              hour=bot._closing_time,
                              tzinfo=bot._local_tz)
        delta = end - end_of_day
        next_day = end_of_day + timedelta(
            hours=(bot._opening_time - bot._closing_time) % 24
        )
        # This may land on a weekend, so march to the next weekday
        while not during_business_hours(next_day, bot):
            next_day += timedelta(days=1)
        end = next_day + delta
    return end


def create_new_alert(dbclient, title, ldap, description,
                     reason, url='N/A', key=None):
    # type: (str, str, str, str, str, str) -> None
    '''
    Creates a new alert in the SQL DB with an optionally random hash.
    '''
    # Generate random key if none provided
    if key is None:
        key = str(binascii.hexlify(os.urandom(32)))

    # Insert that into the database as a new alert
    dbclient.execute(
        'new_alert_alerts',
        (
            key, ldap, title, description, reason, url
        )
    )
    # key, comment, performed, authenticated
    dbclient.execute('new_alert_user_response', (key, '', 0, 0))

    dbclient.execute('new_alert_status', (key, StatusLevel.OPEN.value))
