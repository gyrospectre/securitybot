from logging import (
    basicConfig as logConfig, getLogger,
    CRITICAL, ERROR, WARNING, INFO, DEBUG
)

from securitybot import loader
from securitybot.bot import SecurityBot
from securitybot.exceptions import ConfigException

def main():
    # Load our config first
    config = loader.load_yaml('config/bot.yaml')

    # Setup logging
    level = config['logging']['level']
    if level not in ['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']:
        raise ConfigException('Invalid logging level - {}'.format(level))

    logConfig(level=level,
                        format='[%(asctime)s %(levelname)s] %(message)s')
    getLogger('requests').setLevel(level)
    getLogger('usllib3').setLevel(level)

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
