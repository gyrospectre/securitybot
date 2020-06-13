'''
A wrapper for securitybot to use AWS SimpleDB for it's database.
'''
__author__ = 'Bill Mahony'

import pytz
import logging

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
        self._domain_prefix = config['domain_prefix']
        self._tables = config.get('tables', None)
        self.queries = ''

        self._client = client('sdb')
        self._create_tables()

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

    def _create_tables(self):
        '''
        Create all tables (domains) in list, if they don't already exist
        '''
        for table in self._tables:
            self._client.create_domain(
                DomainName='{}.{}'.format(self._domain_prefix, table)
            )

    def delete_table(self, table):
        '''
        Deletes a table (domain in SDB)
        '''
        try:
            domain = '{}.{}'.format(
                self._domain_prefix,
                table
            )
            result = self._client.delete_domain(
                DomainName=domain
            )
        except Exception as e:
            logging.error("Domain '{}' deletion failed! ({})".format(domain, e))
            return False, e
        
        return True, 'ok'

    #
    # Conversion Helper Functions
    #

    def _format_response(self, dictofdict, fields,
                         timefields=[], boolfields=[]):
        # first value is the primary key
        response = []
        for k, v in dictofdict.items():
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

    def _dict_to_items(self, attribdict, replace=False):
        attribs = []     # list of dicts, with the dict the attribs
        items = []       # list of item names
        for item, values in attribdict.items():
            items.append(item)
            attrib_entry = []
            for key, value in values.items():
                att = {
                    'Name': key,
                    'Value': str(value),
                }
                if replace:
                    att['Replace'] = True

                attrib_entry.append(att)

            attribs.append(attrib_entry)
        return items, attribs

    def _params_to_items(self, fieldnames, values,
                         timefields=[], boolfields=[], replace=True):
        '''
        Taks a list of fieldnames, and a list of values
        and maps the two into a dict
        '''
        record = {}
        prikey = values[0]

        for index, field in enumerate(fieldnames):
            if index > 0:
                if field in timefields:
                    record[prikey][field] = datetime.strptime(
                        values[index], TIME_FORMAT
                    )
                elif field in boolfields:
                    record[prikey][field] = bool(values[index])
                else:
                    record[prikey][field] = values[index]
            else:
                record[prikey] = {}

        return self._dict_to_items(
            attribdict=record,
            replace=replace
        )

    #
    # SQL Like Helper Functions
    #

    def _select(self, fields, table, where=""):
        if where != '':
            append = ' where {}'.format(where)
        else:
            append = ''

        rows = self._client.select(
            SelectExpression="select {} from `{}.{}` {}".format(
                fields,
                self._domain_prefix,
                table,
                append
            ),
            ConsistentRead=True
        )
        return self._items_to_dict(rows)

    def _delete(self, items, attribs, table):
        for idx, item in enumerate(items):
            self._client.delete_attributes(
                ItemName=item,
                Attributes=attribs[idx],
                DomainName='{}.{}'.format(self._domain_prefix, table)
            )

        return True

    def _insert(self, items, attribs, table):
        for idx, item in enumerate(items):
            self._client.put_attributes(
                ItemName=item,
                Attributes=attribs[idx],
                DomainName='{}.{}'.format(self._domain_prefix, table)
            )

        return True

    #
    # Query replacements
    #

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

        if self._delete(
            items=ignored_items,
            attribs=item_attribs,
            table='ignored'
        ) is True:
            logging.debug('Removed {} items from ignored list.'.format(
                len(ignored_items)
                )
            )
            return True
        else:
            logging.error('Could not remove {} items from ignored list.'.format(
                len(ignored_items))
            )
            return False

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
            fields=['ldap', 'title', 'reason'],
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
        fields = ['ldap', 'title', 'reason', 'until']
        ignored_items, item_attribs = self._params_to_items(
            fieldnames=fields,
            values=params,
            timefields=['until'],
            replace=True
        )

        if self._insert(
            items=ignored_items,
            attribs=item_attribs,
            table='ignored'
        ) is True:
            logging.debug('Added {} items to the ignored list.'.format(
                len(ignored_items))
            )
            return True
        else:
            logging.error('Could not add {} items to the ignored list.'.format(
                len(ignored_items))
            )
            return False

        logging.debug('Ignored alert {} for user {}'.format(
            params[1], params[0])
        )

    def _blacklist_list(self, params=None):
        '''
        SELECT * FROM blacklist
        '''
        # Only grab new alerts
        blacklisted = self._select(
            fields='*',
            table='blacklist',
        )

        return self._format_response(
            dictofdict=blacklisted,
            fields=['ldap']
        )

    def _blacklist_add(self, params):
        '''
        INSERT INTO blacklist (ldap) VALUES (%s)
        '''
        fields = ['ldap', 'blacklist_time']
        # Add a timestamp
        params = list(params)
        params.append(datetime.now(tz=pytz.utc).strftime(TIME_FORMAT))

        items, attribs = self._params_to_items(
            fieldnames=fields,
            values=params,
            replace=True
        )

        if self._insert(
            items=items,
            attribs=attribs,
            table='blacklist'
        ) is True:
            logging.debug('Added {} to the blacklist.'.format(params[0]))
            return True
        else:
            logging.error('Could not add {} items to the blacklist.'.format(
                params[0])
            )
            return False

    def _blacklist_remove(self, params):
        '''
        DELETE FROM blacklist WHERE ldap = %s
        '''
        entries = self._select(
            fields='*',
            table='blacklist',
            where="ldap = '{}'".format(params[0])
        )
        items, attribs = self._dict_to_items(entries)

        if self._delete(
            items=items,
            attribs=attribs,
            table='blacklist'
        ) is True:
            logging.debug('Removed {} items from blacklist.'.format(
                len(items)
                )
            )
            return True
        else:
            logging.error('Could no remove {} items from blacklist.'.format(
                len(items))
            )
            return False

    def _new_alert_status(self, params):
        '''
        INSERT INTO alert_status (hash, status) VALUES (UNHEX(%s), %s)
        '''
        fields = ['hash', 'status']
        items, attribs = self._params_to_items(
            fieldnames=fields,
            values=params,
            replace=True
        )

        if self._insert(
            items=items,
            attribs=attribs,
            table='alert_status'
        ) is True:
            logging.debug('Added {} items to the alert status list.'.format(
                len(items))
            )
            return True
        else:
            logging.error('Could not add {} items to alert status.'.format(
                len(items))
            )
            return False

    def _new_alert_alerts(self, params):
        '''
        INSERT INTO alerts
            (hash, ldap, title, description, reason, url, event_time)
        VALUES (UNHEX(%s), %s, %s, %s, %s, %s, NOW())
        '''
        fields = [
            'hash', 'ldap', 'title', 'description',
            'reason', 'url', 'event_time'
        ]

        # Add a timestamp
        params = list(params)
        params.append(datetime.now(tz=pytz.utc).strftime(TIME_FORMAT))

        items, attribs = self._params_to_items(
            fieldnames=fields,
            values=params,
            replace=True
        )

        if self._insert(
            items=items,
            attribs=attribs,
            table='alerts'
        ) is True:
            logging.debug('Added {} items to the alert status list.'.format(
                len(items))
            )
            return True
        else:
            logging.error('Could not add {} items to alert status.'.format(
                len(items))
            )
            return False

    def _new_alert_user_response(self, params):
        '''
        INSERT INTO user_responses (hash, comment, performed, authenticated)
        VALUES (UNHEX(%s), '', false, false)
        '''
        fields = ['hash', 'comment', 'performed', 'authenticated']
        items, attribs = self._params_to_items(
            fieldnames=fields,
            values=params,
            replace=True
        )

        if self._insert(
            items=items,
            attribs=attribs,
            table='user_responses'
        ) is True:
            logging.debug('Added {} items to the user response list.'.format(
                len(items))
            )
            return True
        else:
            logging.error('Could not add {} items to user response.'.format(
                len(items))
            )
            return False

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
        # Only grab new alerts
        alert_status = self._select(
            fields='*',
            table='alert_status',
            where="status = '{}'".format(params[0])
        )
        alerts = self._select(fields='*', table='alerts')
        user_responses = self._select(fields='*', table='user_responses')

        # Join responses and status to alerts that are new
        for k, v in user_responses.items():
            if k in alert_status:
                for attrib, value in v.items():
                    alert_status[k][attrib] = value
        for k, v in alerts.items():
            if k in alert_status:
                for attrib, value in v.items():
                    alert_status[k][attrib] = value

        return self._format_response(
            dictofdict=alert_status,
            fields=[
                'hash', 'title',
                'ldap', 'reason',
                'description', 'url',
                'event_time', 'performed',
                'comment', 'authenticated',
                'status'],
            timefields=['event_time'],
            boolfields=['status']
        )

    def _set_status(self, params=None):
        '''
        UPDATE alert_status
        SET status=%s
        WHERE hash=UNHEX(%s)
        '''
        # Due to the SQL query, fields are reversed, hash is pri key
        # Turn it into a list and reverse it, so we can reuse our
        # existing function
        params = list(params)
        params.reverse()

        return self._new_alert_status(params)

    def _set_response(self, params=None):
        '''
        UPDATE user_responses
        SET comment=%s,
            performed=%s,
            authenticated=%s
        WHERE hash=UNHEX(%s)
        '''
        # Grab the hash from the end of the list and insert at the
        # start so we can reuse our existing function
        new_params = list(params)
        hash = new_params.pop()
        new_params.insert(0, hash)

        return self._new_alert_user_response(new_params)
