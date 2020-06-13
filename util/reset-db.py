import sys
sys.path.append("..")

from time import sleep

from securitybot import loader


def main():
    config = loader.load_yaml('../config/bot.yaml')

    db_provider = config['database']['provider']
    tablelist = config['database']['tables']

    try:
        config['database'][db_provider]['queries_path'] = '../{}'.format(
            config['database'][db_provider]['queries_path']
        )
    except:
        pass

    # Load our secrets
    secrets_provider = config['secretsmgmt']['provider']

    secretsclient = loader.build_secrets_client(
        secrets_provider=secrets_provider,
        connection_config=config['secretsmgmt'][secrets_provider]
    )
    try:
        loader.add_secrets_to_config(
            smclient=secretsclient,
            secrets=config['secretsmgmt']['secrets'],
            config=config
        )
    except Exception as error:
        raise SecretsException(
            'Failed to load secrets! {}'.format(error)
        )
    
    dbclient = loader.build_db_client(
        db_provider=db_provider,
        connection_config=config['database'][db_provider],
        tables=tablelist
    )

    for table in tablelist:
        result, reason = dbclient.delete_table(table=table)
        if result is True:
            print("Table '{}' deleted ({})".format(table, reason))
        else:
            print("Table '{}' deletion failed! ({})".format(table, reason))

    print("Tables deleted.")

if __name__ == '__main__':
    main()

