import boto3
import base64
import operator
import os
import uuid
import logging
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')

device_group_user_integrations_table = dynamodb.Table(os.environ['DEVICE_GROUP_USERS_INTEGRATIONS_TABLE'])
integrations_table = dynamodb.Table(os.environ['INTEGRATIONS_TABLE'])


class Integration:
    def __init__(self, id, name, function_name):
        self.id = id
        self.name = name
        self.function_name = function_name


def get_integrations():
    """Get the available integrations.

    Returns
    -------
    List[Integration]
        A list of integrations.
    """
    response = integrations_table.scan()
    items = response['Items']

    if not items:
        return []

    integrations = [
        Integration(item['integrationId'], item['name'], item['functionName']) for item in items
    ]
    return integrations
