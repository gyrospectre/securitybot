from securitybot import loader

PATH_ROOT = 'securitybot'


def main():
    config = loader.load_yaml('config/bot.yaml')

    secrets_provider = config['secretsmgmt']['provider']

    secretsclient = loader.build_secrets_client(
        secrets_provider=secrets_provider,
        connection_config=config['secretsmgmt'][secrets_provider]
    )
    SECRETS = config['secretsmgmt']['secrets']

    for client_type, clients in SECRETS.items():
        client = config[client_type]['provider']
        print('Chosen {} provider is {}.'.format(client_type, client))
        if client in clients:
            fullsecret = {}
            for secret in clients[client]:
                value = input(
                    "Enter value to store for {} secret {}: ".format(
                        client,
                        secret
                    )
                )
                fullsecret[secret] = value

            secretsclient.create_secret(
                name='{}/{}/{}'.format(PATH_ROOT, client_type, client),
                value=fullsecret,
                description='SecurityBot secrets for {} provider {}.'.format(
                    client_type, client
                )
            )
        else:
            print("Client not found!")

    print('Finished.')


if __name__ == '__main__':
    main()
