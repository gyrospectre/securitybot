#!/usr/bin/env python
import logging

from securitybot.bot import SecurityBot
from securitybot.chat.slack import Slack
from securitybot.tasker import Tasker
from securitybot.auth.duo import DuoAuth
from securitybot.auth.okta import OktaAuth
from securitybot.db.engine import DbEngine

from securitybot.config import config

import duo_client

from okta import UsersClient

from sys import argv


def init():
    # Setup logging
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s %(levelname)s] %(message)s')
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('usllib3').setLevel(logging.WARNING)
    if len(argv) > 1 and argv[1] != "":
        config.load_config(argv[1])
    else:
        config.load_config('config/bot.yaml')

    # Load preferred auth provider
    module = 'securitybot.auth.{}'.format(config['auth']['provider'])
    submodule = config[config['auth']['provider']]['package']
    MFAuth = getattr(__import__(module, fromlist=[submodule]), submodule)

def main():
    init()

    # Create components needed for SecurityBot
    duo_api = duo_client.Auth(
        ikey=config['duo']['ikey'],
        skey=config['duo']['skey'],
        host=config['duo']['endpoint']
    )
    okta_client = UsersClient(
        base_url='https://{}'.format(config['okta']['endpoint']),
        api_token=config['okta']['token']
    )

    duo_builder = lambda name: DuoAuth(duo_api, name)
    okta_builder = lambda name: OktaAuth(okta_client, name)

    auth = okta_builder
    print(duo_builder)
    try:
        # Initialise DbEngine here
        DbEngine(config['database'])
    except KeyError:
        logging.error('No database configuration')
        raise

    chat = Slack(config['slack'])
    tasker = Tasker()

    sb = SecurityBot(chat, tasker, auth, config['slack']['reporting_channel'])
    sb.run()

if __name__ == '__main__':
    main()
