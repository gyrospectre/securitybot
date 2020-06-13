import yaml
import logging

from importlib import import_module

from securitybot.auth.auth import BaseAuthClient

from securitybot.chat.chat import BaseChatClient

from securitybot.db.database import BaseDbClient

from securitybot.secretsmgmt.secretsmgmt import BaseSecretsClient

from securitybot.tasker import Tasker

from securitybot.exceptions import (
    InvalidAuthProvider, InvalidChatProvider, 
    InvalidDatabaseProvider, InvalidSecretsProvider
)


def load_secrets_client(secrets_provider):
    try:
        sanitized_provider = secrets_provider.lower()
        module_name = 'securitybot.secretsmgmt.{}'.format(
            sanitized_provider
        )
        module = import_module(module_name)
        client = getattr(module, 'SecretsClient')

        if not issubclass(client, BaseSecretsClient):
            raise AttributeError(
                '{}.Client is not an SecretsClient Provider'.format(
                    module_name
                )
            )

        return client
    except (ModuleNotFoundError, AttributeError) as e:
        raise InvalidSecretsProvider(
            'Secrets Management Provider for "{}" is not available: {}'.format(
                secrets_provider, e
            )
        )


def build_secrets_client(secrets_provider, connection_config):
    secrets_class = load_secrets_client(secrets_provider)

    return secrets_class(
        connection_config
    )


def add_secrets_to_config(smclient, secrets, config):
    for client_type, clients in secrets.items():
        client = config[client_type]['provider']

        if client in clients:
            logging.debug(
                "About to fetch secret 'securitybot/{}/{}'".format(
                    client_type,
                    client
                )
            )
            scrt_raw = smclient.get_secret(
                'securitybot/{}/{}'.format(
                    client_type,
                    client
                )
            )
            for scrt_name in secrets[client_type][client]:
                config[client_type][client][scrt_name] = scrt_raw[scrt_name]
        else:
            logging.debug(
                'No secrets for {} provider {}'.format(
                    client_type, client
                )
            )

    return True


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


def build_auth_client(auth_provider, connection_config,
                      reauth_time, auth_attrib):
    auth_class = load_auth_client(auth_provider)

    return auth_class(
        connection_config,
        reauth_time,
        auth_attrib
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
        raise InvalidChatProvider(
            'Chat Provider for "{}" is not available: {}'.format(
                chat_provider, e
            )
        )


def build_chat_client(chat_provider, connection_config):
    chat_class = load_chat_client(chat_provider)

    return chat_class(
        connection_config
    )


def build_tasker(dbclient):
    return Tasker(dbclient)


def load_db_client(db_provider):
    try:
        sanitized_provider = db_provider.lower()
        module_name = 'securitybot.db.{}'.format(
            sanitized_provider
        )
        module = import_module(module_name)
        client = getattr(module, 'DbClient')

        if not issubclass(client, BaseDbClient):
            raise AttributeError(
                '{} is not a Db Provider'.format(module_name)
            )

        return client
    except (ModuleNotFoundError, AttributeError) as e:
        raise InvalidDatabaseProvider(
            'DB Provider for "{}" is not available: {}'.format(
                db_provider, e
            )
        )


def build_db_client(db_provider, connection_config, tables):
    db_class = load_db_client(db_provider)
    connection_config['tables'] = tables

    return db_class(
        config=connection_config,
        queries=load_yaml(connection_config.get('queries_path', None))
    )


def load_yaml(path):
    if path:
        return yaml.safe_load(open(path))
    else:
        return None
