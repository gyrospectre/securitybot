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

    def _format_response(self, dictofdict, fields, timefields=[], boolfields=[]):
        #first value is the primary key
        response = []
        for k,v in dictofdict.items():
            line = []
            line.append(k)
            for field in fields[1:]:
                if field in timefields:
                    line.append(
                        datetime.strptime(dictofdict[k][field], TIME_FORMAT)
                    )
                elif field in boolfields:
                    line.append(bool(dictofdict[k][field]))
                else:
                    line.append(dictofdict[k][field])

            response.append(line)

        return response

    def _items_to_dict(self, items):
        # {
        #   'itemname1': {
        #       'aname': 'ldap',
        #       'avalue': 'username1'
        #   },
        #   'itemname2': {
        #       'aname': 'hash',
        #       'avalue': '1234abcd'
        #   }
        # }
        dictofdicts = {}
        try:
            for item in items['Items']:
                itemdict = {}
                for attrib in item['Attributes']:
                    itemdict[attrib['Name']] = attrib['Value']

                dictofdicts[item['Name']] = itemdict

        except KeyError:
            # No items to fetch
            pass

        return dictofdicts        

    def _dict_to_items(self, attribdict):
        attribs=[] #list of dicts, with the dict the attribs
        items=[] #list of item names
        for item,values in attribdict.items():
            items.append(item)
            attrib_entry=[]
            for key, value in values.items():
                attrib_entry.append(
                    {
                        'Name': key,
                        'Value': str(value),
                    }
                )
            attribs.append(attrib_entry)
        print('here 5 {} {}'.format(items, attribs))
        return items, attribs

    def _select(self, fields, table, where=""):
 
        if where != '':
            append =  ' where {}'.format(where)
        else:
            append = ''

        rows = self._client.select(
            SelectExpression="select {} from `{}.{}`".format(
                fields,
                self._domain_prefix,
                table,
                append
            ),
            ConsistentRead=True         
        )
        print('here: {}'.format(self._items_to_dict(rows)))
        return self._items_to_dict(rows)

    def _delete(self, fields, table, where=""):
 
        rows = self._select(
            fields=fields,
            table=table,
            where=where
        )

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

        self._client.put_attributes(
        
            DomainName=domain,
            ItemName=item,
            Attributes=attribs
        )

        rows = self._client.select(
            SelectExpression="select {} from `{}.{}`".format(
                fields,
                self._domain_prefix,
                table,
                append
            ),
            ConsistentRead=True         
        )
        return self._items_to_dict(rows)
        

    def _update_ignored_list(self, params=None):
        '''
        DELETE FROM ignored WHERE until <= NOW()
        '''
        now = datetime.now(tz=pytz.utc).strftime(TIME_FORMAT)

        ignored = self._select(
            fields='*',
            table='ignored',
            where="until <= '{}'".format(now)
        )
        ignored_items, item_attribs = self._dict_to_items(ignored)
        print('here4: {}'.format(ignored_items))
        for idx, item in enumerate(ignored_items):
            self._client.delete_attributes(
                ItemName=item,
                Attributes=item_attribs[idx],
                DomainName='{}.ignored'.format(self._domain_prefix)
            )
        logging.debug('Removed {} items from ignored list.'.format(len(ignored_items)))

    def _get_ignored(self, params):
        '''
        SELECT title, reason FROM ignored WHERE ldap = %s
        '''

        ignored = self._select(
            fields='*',
            table='ignored',
            where="ldap = '{}'".format(params[0])
        )

        ignored_list = self._format_response(
            dictofdict=ignored,
            fields=['ldap','title', 'reason'],
        )

        if len(ignored_list) > 0:
            logging.debug('Got ignored alerts for user {}'.format(params[0]))

        return ignored_list

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
        alerts = self._select(fields='*', table='alerts')
        user_responses = self._select(fields='*', table='user_responses')
        alert_status = self._select(fields='*', table='alert_status')

        print(alerts)
        # Join responses and status to alerts
        for k,v in user_responses.items():
            if k in alerts:
                for attrib,value in v.items():
                    alerts[k][attrib] = value
        for k,v in alert_status.items():
            if k in alerts:
                for attrib,value in v.items():
                    alerts[k][attrib] = value

        return self._format_response(
            dictofdict=alerts,
            fields=['hash','title', 'ldap', 'reason', 'description', 'url', 'event_time', 'performed', 'comment', 'authenticated', 'status'],
            timefields=['event_time'],
            boolfields=['status']
        )

#        return ((
#            finalalert['hash'],
#            finalalert['title'],
#            finalalert['ldap'],
#            finalalert['reason'],
#            finalalert['description'],
#            finalalert['url'],
#            #datetime.strptime(finalalert['event_time'], TIME_FORMAT),
#            finalalert['performed'],
#            finalalert['comment'],
#            finalalert['authenticated'],
#            bool(finalalert['status'])
#        ), )

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