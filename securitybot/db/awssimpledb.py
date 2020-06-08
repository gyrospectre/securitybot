'''
A wrapper for the securitybot use AWS SimpleDB for it's database.
'''
__author__ = 'Bill Mahony'

import pytz
import logging
import uuid

from datetime import datetime

from securitybot.db.database import BaseDbClient

from securitybot.exceptions import DbException

from boto3 import client

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S%z'


class DbClient(BaseDbClient):

    def __init__(self, config, queries):
        '''
        Initializes the DynamoDB connection to be used for the bot.

        '''
        self._client = client('sdb')
        self._domain_prefix = config['domain_prefix']

        self.queries = ''
        

    def execute(self, query, params=None):
        '''
        Executes a given SQL query with some possible params.

        Args:
            query (str): The query to perform.
            params (Tuple[str]): Optional parameters to pass to the query.
        Returns:
            Tuple[Tuple[str]]: The output from the SQL query.
        '''
        if params is None:
            params = ()
        try:
            logging.debug('Executing: ' + query + str(params))
            result = getattr(self, '_{}'.format(query))(
                params=params
            )
            rows = result
        except Exception as error:
            raise DbException(error)
            
        logging.debug('Result: ' + str(rows))
        return rows

    def _put_attribs(self, item, attribs, domain):

        self._client.put_attributes(
            DomainName=domain,
            ItemName=item,
            Attributes=attribs
        )

    def _get_attribs(self, item, attrib_names, domain):

        response = self._client.get_attributes(
            DomainName=domain,
            ItemName=item,
            AttributeNames=attrib_names,
            ConsistentRead=True
        )

        return response
    
    def _select(self, expression):
        response = self._client.select(
            SelectExpression=expression,
            ConsistentRead=True
        )
        return response
    
    def _update_ignored_list(self, params=None):
        '''
        DELETE FROM ignored WHERE until <= NOW()
        '''
        now = datetime.now(tz=pytz.utc).strftime(TIME_FORMAT)
        ignored = self._select(
            expression="select * from `{}.ignored` where until <= '{}'".format(
                self._domain_prefix,
                now
                )
            )

        # Get old ignoredalerts
        to_delete={}
        try:
            for alert in ignored['Items']:
                to_delete[alert['Name']] = {}

                for item in alert['Attributes']:
                    to_delete[alert['Name']][item['Name']] = item['Value']

        except KeyError:
            # No ignored alerts to delete
            return

        for item, v in to_delete.items():
            attribs=[]
            for name, value in v.items():
                attribs.append(
                    {
                        'Name': name,
                        'Value': str(value),
                        'Replace': True
                    }
                )
            self._put_attribs(
                item=item,
                attribs=attribs,
                domain='{}.ignored'.format(self._domain_prefix)
            )
            logging.debug('Removed {} from ignored list.'.format(item))

    def _get_ignored(self, params):
        '''
        SELECT title, reason FROM ignored WHERE ldap = %s
        '''
        ignored = self._select(
            expression="select * from `{}.ignored` where ldap = '{}'".format(
                self._domain_prefix,
                params[0]
                )
            )
        final = {}
        # Get ignored alerts
        try:
            for alert in ignored['Items']:
                for item in alert['Attributes']:
                    final[item['Name']] = item['Value']
        except KeyError:
            # No alerts to fetch
            logging.debug('No ignored alerts found for user {}'.format(params[0]))
            return []

        logging.debug('Got ignored alert {} for user {}'.format(final['title'], params[0]))

        return ((
            final['title'],
            final['reason'],
        ), )

    def _ignore_task(self, params):
        '''
        INSERT INTO ignored (ldap, title, reason, until)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE reason=VALUES(reason), until=VALUES(until)        
        '''
        item = str(uuid.uuid4())
        fields = ['ldap', 'title', 'reason', 'until']
        attribs=[]
        for index, value in enumerate(params):
            attribs.append(
                {
                    'Name': fields[index],
                    'Value': str(value),
                    'Replace': True
                }
            )
        print("here: {}".format(params))
        self._put_attribs(
            item=item,
            attribs=attribs,
            domain='{}.ignored'.format(self._domain_prefix)
        )
        logging.debug('Ignored alert {} for user {}'.format(params[1], params[0]))

    def _blacklist_list(self, params=None):
        return []

    def _blacklist_add(self):
        return []

    def _blacklist_remove(self):
        return []

    def _new_alert_status(self, params):
        '''
        INSERT INTO alert_status (hash, status) VALUES (UNHEX(%s), %s)
        '''
        primaryfield = 'hash'
        fields = ['hash', 'status']
        attribs=[]
        for index, value in enumerate(params):
            if fields[index] is primaryfield:
                item = value.decode("utf-8")
            else:
                attribs.append(
                    {
                        'Name': fields[index],
                        'Value': str(value),
                        'Replace': True
                    }
                )
        self._put_attribs(
            item=item,
            attribs=attribs,
            domain='{}.alert_status'.format(self._domain_prefix)
        )
        logging.debug('Created new alert status: {}'.format(attribs))

    def _new_alert_alerts(self, params):
        '''
        INSERT INTO alerts (hash, ldap, title, description, reason, url, event_time)
        VALUES (UNHEX(%s), %s, %s, %s, %s, %s, NOW())
        '''
        primaryfield = 'hash'
        fields = ['hash', 'ldap', 'title', 'description', 'reason', 'url']
        attribs=[]
        for index, value in enumerate(params):
            if fields[index] is primaryfield:
                item = value.decode("utf-8")
            else:
                attribs.append(
                    {
                        'Name': fields[index],
                        'Value': str(value),
                        'Replace': True
                    }
                )
        # Add a timestamp
        attribs.append(
            {
                'Name': 'event_time',
                'Value': datetime.now(tz=pytz.utc).strftime(TIME_FORMAT),
                'Replace': True
            }
        )
        self._put_attribs(
            item=item,
            attribs=attribs,
            domain='{}.alerts'.format(self._domain_prefix)
        )
        logging.debug('Created new alert: {} - {}'.format(item, attribs))

        return True
    
    def _new_alert_user_response(self, params):
        '''
        INSERT INTO user_responses (hash, comment, performed, authenticated)
        VALUES (UNHEX(%s), '', false, false)
        '''
        primaryfield = 'hash'
        fields = ['hash', 'comment', 'performed', 'authenticated']
        defaults = {
            'comment': '',
            'performed': '0',
            'authenticated': '0'
        }
        attribs=[]
        for index, value in enumerate(params):
            if fields[index] is primaryfield:
                item = value.decode("utf-8")
            else:
                attribs.append(
                    {
                        'Name': fields[index],
                        'Value': str(value),
                        'Replace': True
                    }
                )
        for fieldname, value in defaults.items():
            attribs.append(
                {
                    'Name': fieldname,
                    'Value': value,
                    'Replace': True
                }
            )

        self._put_attribs(
            item=item,
            attribs=attribs,
            domain='{}.user_responses'.format(self._domain_prefix)
        )
        logging.debug('Created new user response: {} - {}'.format(item, attribs))

        return True
    
    def _get_alerts(self, params=None):
        '''
        SELECT HEX(alerts.hash),
            title,
            ldap,
            reason,
            description,
            url,
            event_time,
            performed,
            comment,
            authenticated,
            status
        FROM alerts
        JOIN user_responses ON alerts.hash = user_responses.hash
        JOIN alert_status ON alerts.hash = alert_status.hash
        WHERE status = %s
        '''
        alerts = self._select(
            expression='select * from `{}.alerts`'.format(self._domain_prefix))
        user_responses = self._select(
            expression='select * from `{}.user_responses`'.format(self._domain_prefix))
        alert_status = self._select(
            expression='select * from `{}.alert_status`'.format(self._domain_prefix))

        finalalert={}
        # Get alerts
        try:
            for alert in alerts['Items']:
                finalalert['hash'] = alert['Name']

                for item in alert['Attributes']:
                    finalalert[item['Name']] = item['Value']
        except KeyError:
            # No alerts to fetch
            return []

        # Add User Responses
        for response in user_responses['Items']:
            if response['Name'] == finalalert['hash']:
                for item in response['Attributes']:
                    finalalert[item['Name']] = item['Value']

        # Add Alert statuses
        for status in alert_status['Items']:
            if status['Name'] == finalalert['hash']:
                for item in status['Attributes']:
                    finalalert[item['Name']] = item['Value']

        
        return ((
            finalalert['hash'],
            finalalert['title'],
            finalalert['ldap'],
            finalalert['reason'],
            finalalert['description'],
            finalalert['url'],
            datetime.strptime(finalalert['event_time'], TIME_FORMAT),
            finalalert['performed'],
            finalalert['comment'],
            finalalert['authenticated'],
            bool(finalalert['status'])
        ), )

    def _set_status(self, params=None):
        '''
        UPDATE alert_status
        SET status=%s
        WHERE hash=UNHEX(%s)
        '''
        status = params[0]
        statushash = params[1]

        attribs=[
            {
                'Name': 'status',
                'Value': str(status),
                'Replace': True
            }
        ]

        self._put_attribs(
            item=statushash,
            attribs=attribs,
            domain='{}.alert_status'.format(self._domain_prefix)
        )
        logging.debug('Updated status for alert: {}'.format(statushash))

    def _set_response(self, params=None):
        pass