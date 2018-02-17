import boto3
import operator
import os
import uuid
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


cognito_idp = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')

device_group_table = dynamodb.Table('MagicMirror-dev-device-group')
device_group_users_table = dynamodb.Table('MagicMirror-dev-device-group-users')


class DeviceGroup:

    def __init__(self, id, name):
        self.id = id
        self.name = name


class DeviceGroupUser:

    def __init__(self, id, group_id, owner=False):
        self.id = id
        self.group_id = group_id
        self.owner = owner


class DeviceGroupNotFoundException(Exception):
    pass


class DeviceGroupAlreadyExistsException(Exception):
    pass


class UserNotInDeviceGroupException(Exception):
    pass


class UserAlreadyInDeviceGroupException(Exception):
    pass


def get_cognito_user_devices(user_id):
    user = cognito_idp.list_users(
        UserPoolId=os.environ['UserPoolId'],
        Filter=f'sub = "{user_id}"'
    )['Users'][0]
    response = cognito_idp.admin_list_devices(
        UserPoolId=os.environ['UserPoolId'],
        Username=user['Username']
    )
    for device in response['Devices']:
        device['DeviceAttributes'] = {attr['Name']: attr['Value'] for attr in device['DeviceAttributes']}
    return response['Devices'][0]


def verify_users_used_same_device(user_id1, user_id2):
    # TODO: only if remembered by owner??
    def get_device_keys(id):
        return map(operator.itemgetter('DeviceKey'), get_cognito_user_devices(id))
    user1_device_keys = get_device_keys(user_id1)
    user2_device_keys = get_device_keys(user_id2)
    return bool(set(user1_device_keys) & set(user2_device_keys))


def is_member(user_id, group_id):
    try:
        get_user_in_device_group(user_id, group_id)
        return True
    except UserNotInDeviceGroupException:
        return False


def is_owner(user_id, group_id):
    try:
        user = get_user_in_device_group(user_id, group_id)
        if user.owner:
            return True
    except UserNotInDeviceGroupException:
        pass
    return False


def get_device_group(group_id):
    """Get a device group by its id.

    Parameters
    ----------
    group_id: str
        The unique id of the group.

    Returns
    -------
    DeviceGroup

    Raises
    ------
    DeviceGroupNotFoundException
    """
    response = device_group_table.get_item(
        Key={
            'groupId': group_id
        }
    )
    if 'Item' not in response:
        raise DeviceGroupNotFoundException(f"DeviceGroup(id='{group_id}') not found.")
    item = response['Item']
    return DeviceGroup(item['groupId'], item['groupName'])


def delete_device_group(group_id):
    """Delete a device group by its id.

    Parameters
    ----------
    group_id: str
        The unique id of the group.

    Raises
    ------
    DeviceGroupNotFoundException
    """
    try:
        device_group_table.delete_item(
            Key={
                'groupId': group_id
            },
            ConditionExpression="attribute_exists(groupId)"
        )
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise DeviceGroupNotFoundException(f"DeviceGroup(id='{group_id}') not found.") from e
        else:
            raise


def update_device_group(device_group):
    """Update an existing device group.

    Parameters
    ----------
    device_group: DeviceGroup
        The device group to update.

    Raises
    ------
    DeviceGroupNotFoundException
    """
    try:
        device_group_table.update_item(
            Key={
                'groupId': device_group.id
            },
            UpdateExpression="set groupName = :n",
            ExpressionAttributeValues={
                ':n': device_group.name
            },
            ConditionExpression="attribute_exists(groupId)",
            ReturnValues="UPDATED_NEW"
        )
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise DeviceGroupNotFoundException(f"DeviceGroup(id='{device_group.id}') not found.") from e
        else:
            raise


def get_device_groups_by_user(user_id, owner=False):
    """Get the device groups for which a particular user is a member of.

    Parameters
    ----------
    user_id: str
        The unique id of the user.
    owner: bool, optional
        Return only the device groups where the user is the owner.

    Returns
    -------
    List[DeviceGroup]
        A list of device groups for which the user is a member of.
    """
    response = device_group_users_table.query(
        IndexName='useridGSI',
        KeyConditionExpression=Key('userId').eq(user_id)
    )
    items = response['Items']

    if owner:
        items = list(filter(lambda item: item['groupOwner'], items))

    if not items:
        return []

    response = dynamodb.batch_get_item(
        RequestItems={
            device_group_table.table_name: {
                'Keys': [{'groupId': item['groupId']} for item in items],
                'ConsistentRead': True
            }
        }
    )
    items = response['Responses'][device_group_table.table_name]
    device_groups = [DeviceGroup(item['groupId'], item['groupName']) for item in items]
    return device_groups


def create_device_group(name):
    """Creates a new device group with a random id.

    Parameters
    ----------
    name: str
        The name of the group.

    Returns
    -------
    DeviceGroup
        The device group that was created.

    Raises
    ------
    DeviceGroupAlreadyExistsException
    """

    item = {
        'groupId': str(uuid.uuid1()),
        'groupName': name
    }

    try:
        device_group_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(groupId)"
        )
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise DeviceGroupAlreadyExistsException(f"DeviceGroup(id='{item['groupId']}') already exists.") from e
        else:
            raise

    return DeviceGroup(item['groupId'], item['groupName'])


def get_user_in_device_group(user_id, group_id):
    """Get a user in a particular device group.

    Parameters
    ----------
    user_id: str
        The unique id of the user.
    group_id: str
        The unique id of the group.

    Returns
    -------
    DeviceGroupUser
        A users in the device group.

    Raises
    ------
    UserNotInDeviceGroupException
    """
    response = device_group_users_table.get_item(
        Key={
            'groupId': group_id,
            'userId': user_id
        }
    )
    if 'Item' not in response:
        raise UserNotInDeviceGroupException(f"User(id='{user_id}') not in DeviceGroup(id='{group_id}').")
    item = response['Item']
    return DeviceGroupUser(item['userId'], item['groupId'], item['groupOwner'])


def delete_user_in_device_group(user_id, group_id):
    """Delete/remove a user from a device group.

    Parameters
    ----------
    user_id: str
        The unique id of the user.
    group_id: str
        The unique id of the group.

    Raises
    ------
    UserNotInDeviceGroupException
    """
    try:
        device_group_users_table.delete_item(
            Key={
                'groupId': group_id,
                'userId': user_id
            },
            ConditionExpression="attribute_exists(groupId)"
        )
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise UserNotInDeviceGroupException(f"User(id='{user_id}') not in DeviceGroup(id='{group_id}').")
        else:
            raise


def update_user_in_device_group(device_group_user):
    """Update an existing device group user.

    Parameters
    ----------
    device_group_user: DeviceGroupUser
        The device group user to update.

    Raises
    ------
    UserNotInDeviceGroupException
    """
    try:
        device_group_users_table.update_item(
            Key={
                'groupId': device_group_user.group_id,
                'userId': device_group_user.id
            },
            UpdateExpression="set groupOwner = :o",
            ExpressionAttributeValues={
                ':o': device_group_user.owner
            },
            ConditionExpression="attribute_exists(groupId) AND attribute_exists(userId)",
            ReturnValues="UPDATED_NEW"
        )
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise UserNotInDeviceGroupException(f"User(id='{device_group_user.id}') not in DeviceGroup(id='{device_group_user.group_id}').")
        else:
            raise


def get_users_in_device_group(group_id):
    """Get the users in a particular device group.

    Parameters
    ----------
    group_id: str
        The unique id of the group.

    Returns
    -------
    List[DeviceGroupUser]
        A list of users in the device group.
    """
    response = device_group_users_table.query(
        KeyConditionExpression=Key('groupId').eq(group_id)
    )
    items = response['Items']
    groups = [DeviceGroupUser(item['userId'], item['groupId'], item['groupOwner'])
              for item in items]
    return groups


def add_user_to_device_group(user_id, group_id, owner=False):
    """Join/add a user to a device group.

    Parameters
    ----------
    user_id: str
        The unique id of the user.
    group_id: str
        The unique id of the group.
    owner: bool, optional
        Is the user the owner of the group.

    Returns
    -------
    DeviceGroupUser
        The user that was added to the device group.

    Raises
    ------
    UserAlreadyInDeviceGroupException
    DeviceGroupNotFoundException
    """
    get_device_group(group_id)

    item = {
        'groupId': group_id,
        'userId': user_id,
        'groupOwner': owner,
        # 'token': ''  # or auth service?..
    }

    try:
        device_group_users_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(groupId) AND attribute_not_exists(userId)"
        )
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise UserAlreadyInDeviceGroupException(f"User(id='{user_id}') already in DeviceGroup(id='{group_id}').") from e
        else:
            raise

    return DeviceGroupUser(user_id, group_id, owner)