from securitybot import loader


def main():
    config = loader.load_yaml('config/bot.yaml')

    db_provider = config['database']['provider']
    tablelist = config['database']['tables']

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
        print('Failed to load secrets! {}'.format(error))

    dbclient = loader.build_db_client(
        db_provider=db_provider,
        connection_config=config['database'][db_provider],
        tables=tablelist
    )

    for table in tablelist:
        print('Contents of table {}::'.format(table))
        print(dbclient.dump_table(table))


if __name__ == '__main__':
    main()
