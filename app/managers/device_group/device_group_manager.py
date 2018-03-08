import boto3
import base64
import operator
import os
import uuid
import logging
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

cognito_identity = boto3.client('cognito-identity')
cognito_idp = boto3.client('cognito-idp')
dynamodb = boto3.resource('dynamodb')
rekognition = boto3.client('rekognition')

device_group_table = dynamodb.Table(os.environ['DEVICE_GROUP_TABLE'])
device_group_users_table = dynamodb.Table(
    os.environ['DEVICE_GROUP_USERS_TABLE'])
device_group_user_faces_table = dynamodb.Table(
    os.environ['DEVICE_GROUP_USER_FACES_TABLE'])


class DeviceGroup:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class DeviceGroupUser:
    def __init__(self, id, group_id, owner, face_num):
        self.id = id
        self.group_id = group_id
        self.owner = owner
        self.face_num = face_num


class DeviceGroupNotFoundException(Exception):
    pass


class DeviceGroupAlreadyExistsException(Exception):
    pass


class UserNotInDeviceGroupException(Exception):
    pass


class UserAlreadyInDeviceGroupException(Exception):
    pass


class FaceNotInDeviceGroupException(Exception):
    pass


class NoFaceInImageException(Exception):
    pass


def get_cognito_user_devices(user_id):
    user = cognito_idp.list_users(
        UserPoolId=os.environ['UserPoolId'],
        Filter=f'sub = "{user_id}"')['Users'][0]
    response = cognito_idp.admin_list_devices(
        UserPoolId=os.environ['UserPoolId'], Username=user['Username'])
    for device in response['Devices']:
        device['DeviceAttributes'] = {
            attr['Name']: attr['Value']
            for attr in device['DeviceAttributes']
        }
    return response['Devices'][0]


def verify_users_used_same_device(user_id1, user_id2):
    # TODO: only if remembered by owner??
    def get_device_keys(id):
        return map(
            operator.itemgetter('DeviceKey'), get_cognito_user_devices(id))

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
    response = device_group_table.get_item(Key={'groupId': group_id})
    if 'Item' not in response:
        raise DeviceGroupNotFoundException(
            f"DeviceGroup(id='{group_id}') not found.")
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
            Key={'groupId': group_id},
            ConditionExpression="attribute_exists(groupId)")
    except ClientError as e:
        if hasattr(
                e, 'response'
        ) and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise DeviceGroupNotFoundException(
                f"DeviceGroup(id='{group_id}') not found.") from e
        else:
            raise

    delete_face_collection(group_id)


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
            Key={'groupId': device_group.id},
            UpdateExpression="set groupName = :n",
            ExpressionAttributeValues={':n': device_group.name},
            ConditionExpression="attribute_exists(groupId)",
            ReturnValues="UPDATED_NEW")
    except ClientError as e:
        if hasattr(
                e, 'response'
        ) and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise DeviceGroupNotFoundException(
                f"DeviceGroup(id='{device_group.id}') not found.") from e
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
        KeyConditionExpression=Key('userId').eq(user_id))
    items = response['Items']

    if owner:
        items = list(filter(lambda item: item['groupOwner'], items))

    if not items:
        return []

    response = dynamodb.batch_get_item(
        RequestItems={
            device_group_table.table_name: {
                'Keys': [{
                    'groupId': item['groupId']
                } for item in items],
                'ConsistentRead': True
            }
        })
    items = response['Responses'][device_group_table.table_name]
    device_groups = [
        DeviceGroup(item['groupId'], item['groupName']) for item in items
    ]
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

    item = {'groupId': str(uuid.uuid1()), 'groupName': name}

    try:
        device_group_table.put_item(
            Item=item, ConditionExpression="attribute_not_exists(groupId)")
    except ClientError as e:
        if hasattr(
                e, 'response'
        ) and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise DeviceGroupAlreadyExistsException(
                f"DeviceGroup(id='{item['groupId']}') already exists.") from e
        else:
            raise

    create_face_collection(item['groupId'])

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
    response = device_group_users_table.get_item(Key={
        'groupId': group_id,
        'userId': user_id
    })
    if 'Item' not in response:
        raise UserNotInDeviceGroupException(
            f"User(id='{user_id}') not in DeviceGroup(id='{group_id}').")
    item = response['Item']
    face_num = len(get_user_face_ids_in_group(user_id, group_id))
    return DeviceGroupUser(item['userId'], item['groupId'], item['groupOwner'], face_num)


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
            Key={'groupId': group_id,
                 'userId': user_id},
            ConditionExpression="attribute_exists(groupId)")
    except ClientError as e:
        if hasattr(
                e, 'response'
        ) and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise UserNotInDeviceGroupException(
                f"User(id='{user_id}') not in DeviceGroup(id='{group_id}').")
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
            ExpressionAttributeValues={':o': device_group_user.owner},
            ConditionExpression=
            "attribute_exists(groupId) AND attribute_exists(userId)",
            ReturnValues="UPDATED_NEW")
    except ClientError as e:
        if hasattr(
                e, 'response'
        ) and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise UserNotInDeviceGroupException(
                f"User(id='{device_group_user.id}') not in DeviceGroup(id='{device_group_user.group_id}')."
            )
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
        KeyConditionExpression=Key('groupId').eq(group_id))
    items = response['Items']
    groups = [
        DeviceGroupUser(item['userId'], item['groupId'], item['groupOwner'])
        for item in items
    ]
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
            ConditionExpression=
            "attribute_not_exists(groupId) AND attribute_not_exists(userId)")
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            raise UserAlreadyInDeviceGroupException(f"User(id='{user_id}') already in DeviceGroup(id='{group_id}').") from e
        else:
            raise

    return DeviceGroupUser(user_id, group_id, owner, 0)


def register_user_face_in_device_group(user_id, group_id, faces, provider, token):
    face_ids = []

    for face in faces:
        response = rekognition.index_faces(
            CollectionId=group_id,
            Image={'Bytes': base64.b64decode(face.encode('utf-8'))},
            ExternalImageId=user_id,
            DetectionAttributes=[
                'DEFAULT'  # |'ALL',
            ])

        face_id = response['FaceRecords'][0]['Face']['FaceId']
        face_ids.append(face_id)

        # logging.error('register:')
        # logging.error(response)

    with device_group_user_faces_table.batch_writer() as batch:
        for face_id in face_ids:
            batch.put_item(Item={
                'groupId': group_id,
                'faceId': face_id,
                'userId': user_id
            })

    # response = cognito_identity.get_open_id_token_for_developer_identity(
    #     IdentityPoolId=str(os.environ['IDENTITY_POOL_ID']),
    #     # IdentityId=user_id,  # instead of token??
    #     Logins={
    #         os.environ['DEVELOPER_PROVIDER_NAME']: user_id,
    #         provider: token
    #     }
    # )
    #
    # logging.error(response)


def get_user_face_ids_in_group(user_id, group_id):
    response = device_group_user_faces_table.query(
        IndexName='groupIdUserIdGSI',
        KeyConditionExpression=Key('groupId').eq(group_id) & Key('userId').eq(user_id)
    )
    return response['Items']


def auth_user_in_device_group(group_id, face):
    user_id = search_user_face_in_device_group(group_id, face)
    # token, identity_id = get_open_id_token(user_id)
    response = cognito_identity.get_open_id_token_for_developer_identity(
        IdentityPoolId=str(os.environ['IDENTITY_POOL_ID']),
        # IdentityId=user_id,
        Logins={
            os.environ['DEVELOPER_PROVIDER_NAME']: user_id,
        },
        TokenDuration=86400
    )

    # identity_id = response['IdentityId']
    token = response['Token']
    return token


def get_open_id_token(user_id, provider, token):
    # response = cognito_identity.get_open_id_token(
    #     IdentityId=f'eu-west-1:...'
    # )
    response = cognito_identity.get_open_id_token_for_developer_identity(
        IdentityPoolId=str(os.environ['IDENTITY_POOL_ID']),
        # IdentityId=user_id,
        Logins={
            os.environ['DEVELOPER_PROVIDER_NAME']: user_id,
            provider: token
        },
        TokenDuration=86400
    )

    identity_id = response['IdentityId']
    token = response['Token']

    return token, identity_id


def search_user_face_in_device_group(group_id, face):
    try:
        response = rekognition.search_faces_by_image(
            CollectionId=group_id,
            FaceMatchThreshold=95,
            Image={'Bytes': base64.b64decode(face.encode('utf-8'))},
            MaxFaces=5,
        )
    except ClientError as e:
        if hasattr(e, 'response') and e.response['Error']['Code'] == 'InvalidParameterException':
            raise NoFaceInImageException(f"There are no faces in the image. Should be at least 1.") from e
        else:
            raise

    # logging.error('search:')
    # logging.error(response)

    # best_confidence = response['SearchedFaceConfidence']  # even if not chosen..

    try:
        face_id = response['FaceMatches'][0]['Face']['FaceId']
    except IndexError:
        raise FaceNotInDeviceGroupException(
            f"DeviceGroup(id='{group_id}') does not recognise this face.")

    response = device_group_user_faces_table.get_item(Key={
        'groupId': group_id,
        'faceId': face_id
    })

    # logging.error('DDB:')
    # logging.error({'groupId': group_id, 'faceId': face_id})

    if 'Item' not in response:
        raise FaceNotInDeviceGroupException(
            f"DeviceGroup(id='{group_id}') does not recognise this face.")
    user_id = response['Item']['userId']

    # logging.error('user_id:')
    # logging.error(user_id)

    return user_id


def remove_user_face_from_device_group(user_id, group_id):
    # query DDB GSI for userId to get faceId, delete from collection/DDB
    pass


def create_face_collection(group_id):
    rekognition.create_collection(CollectionId=group_id)


def delete_face_collection(group_id):
    # DDB
    rekognition.delete_collection(CollectionId=group_id)
