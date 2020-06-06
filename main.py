import logging

from securitybot.bot import SecurityBot
from securitybot.config import Config


def main():
    # Setup logging
    logging.basicConfig(level=logging.DEBUG,
                        format='[%(asctime)s %(levelname)s] %(message)s')
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('usllib3').setLevel(logging.WARNING)

    config = Config()
    config.load_config('config/bot.yaml')

    # Try and create a bot instance
    try:
        sb = SecurityBot(config=config)

    except KeyError:
        logging.error('Configuration missing')
        raise

    # Run the bot
    sb.run()

if __name__ == '__main__':
    main()
