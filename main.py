#!/usr/bin/env python
import logging

from securitybot.bot import SecurityBot
from securitybot.db.engine import DbEngine
from securitybot.config import config


def main():
    # Setup logging
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s %(levelname)s] %(message)s')
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('usllib3').setLevel(logging.WARNING)

    config.load_config('config/bot.yaml')

    # Connect to DB
    try:
        DbEngine(config['database'])
    except KeyError:
        logging.error('No database configuration')
        raise

    sb = SecurityBot(
        chat=config['chat']['provider'],
        auth=config['auth']['provider'],
    )

    sb.run()

if __name__ == '__main__':
    main()
