'''
Password management using AWS Secrets Manager
'''

__author__ = 'Bill Mahony'


import json

from securitybot.secretsmgmt.secretsmgmt import BaseSecretsClient

from boto3 import client

from botocore.exceptions import ClientError


class SecretsClient(BaseSecretsClient):

    def __init__(self, connection_config) -> None:
        '''
        Args:
            connection_config (Dict): Parameters required to connect to SM
        '''
        self._client = client('secretsmanager')

    def get_secret(self, secret):
        '''
        returns a dict of the secret
        '''
        response = self._client.get_secret_value(
            SecretId=secret
        )

        return json.loads(response['SecretString'])
    
    def create_secret(self, name, value, description=''):
        try:
            response = self._client.create_secret(
                Name=name,
                Description=description,
                SecretString=json.dumps(value),
                Tags=[
                    {
                        'Key': 'createdby',
                        'Value': 'securitybot'
                    },
                ]
            )
        except ClientError as e: 
            if 'ResourceExistsException' == e.__class__.__name__:
                # Secret already exists, just update it
                response = self._client.put_secret_value(
                    SecretId=name,
                    SecretString=json.dumps(value),
                )
                return response
        return response 
