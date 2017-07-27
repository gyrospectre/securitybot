#!/usr/bin/env python
import logging

from securitybot.bot import SecurityBot
from securitybot.chat.slack import Slack
from securitybot.tasker.sql_tasker import SQLTasker
from securitybot.auth.duo import DuoAuth
from securitybot.db.engine import DbEngine
import duo_client
from securitybot.config import config


def init():
    # Setup logging
    config.load_config('config/bot.yaml')
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s %(levelname)s] %(message)s')
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('usllib3').setLevel(logging.WARNING)


def main():
    init()
    # init_sql()

    # Create components needed for SecurityBot
    duo_api = duo_client.Auth(
        ikey=config['duo']['ikey'],
        skey=config['duo']['skey'],
        host=config['duo']['endpoint']
    )
    duo_builder = lambda name: DuoAuth(duo_api, name)
    try:
        # Initialise DbEngine here
        DbEngine(config['database'])
    except KeyError:
        logging.error('No database configuration')
        raise

    chat = Slack(config['slack'])
    tasker = SQLTasker()

    sb = SecurityBot(chat, tasker, duo_builder, config['slack']['reporting_channel'])
    sb.run()

if __name__ == '__main__':
    main()
