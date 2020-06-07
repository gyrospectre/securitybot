import hvac
import os

PATH_ROOT = 'securitybot'

SECRETS = {
    'chat': {
        'slack': [
            'token'
        ]
    },
    'database': {
        'mysql': [
            'user',
            'password'
        ]
    },
    'auth': {
        'okta': [
            'api_token'
        ],
        'duo': [
            'ikey',
            'skey'
        ]
    }
}

vaultClient = hvac.Client(
    url='http://127.0.0.1:8200',
    token=os.environ['VAULT_TOKEN_ID']
)
if not vaultClient.is_authenticated():
    raise Exception('Vault client authentication failed!')
else:
    print('Sucessfully connected to Vault.')

for client_type,clients in SECRETS.items():
    client = input("What {} client would you like to use?: ".format(client_type))
    if client in clients:
        fullsecret = {}
        for secret in clients[client]:
            value = input("Enter value to store for secret {}: ".format(secret))
            fullsecret[secret] = value

        create_response = vaultClient.secrets.kv.v2.create_or_update_secret(
            path='{}/{}/{}'.format(PATH_ROOT, client_type, client),
            secret=fullsecret
        )
        print("Wrote secret {} to path '{}/{}/{}".format(fullsecret, PATH_ROOT, client_type, client))
        if create_response['warnings'] is not None:
            print('with warnings {}'.format(create_response['warnings']))
    else:
        print("That client not found!")

print('Finished.')