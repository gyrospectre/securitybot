from importlib import import_module

from securitybot.config import config

from securitybot.auth.auth import BaseAuthClient

from securitybot.chat.chat import BaseChatClient

from securitybot.tasker import Tasker

from securitybot.exceptions import InvalidAuthProvider


def load_auth_client(auth_provider):
    try:
        sanitized_provider = auth_provider.lower()
        module_name = 'securitybot.auth.{}'.format(
            sanitized_provider
        )
        module = import_module(module_name)
        client = getattr(module, 'AuthClient')

        if not issubclass(client, BaseAuthClient):
            raise AttributeError(
                '{}.Client is not an Auth Provider'.format(module_name)
            )

        return client
    except (ModuleNotFoundError, AttributeError) as e:
        raise InvalidAuthProvider(
            'Auth Provider for "{}" is not available: {}'.format(
                auth_provider, e
            )
        )

def build_auth_client(auth_provider):
    auth_class = load_auth_client(auth_provider)
    connection_config = config['auth'][auth_provider]

    return auth_class(
        connection_config
    )

def load_chat_client(chat_provider):
    try:
        sanitized_provider = chat_provider.lower()
        module_name = 'securitybot.chat.{}'.format(
            sanitized_provider
        )
        module = import_module(module_name)
        client = getattr(module, 'ChatClient')

        if not issubclass(client, BaseChatClient):
            raise AttributeError(
                '{}.Client is not a Chat Provider'.format(module_name)
            )

        return client
    except (ModuleNotFoundError, AttributeError) as e:
        raise InvalidAuthProvider(
            'Chat Provider for "{}" is not available: {}'.format(
                chat_provider, e
            )
        )

def build_chat_client(chat_provider):
    chat_class = load_chat_client(chat_provider)
    connection_config = config['chat'][chat_provider]

    return chat_class(
        connection_config
    )

def build_tasker():
    return Tasker()