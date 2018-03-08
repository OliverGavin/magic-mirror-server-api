import boto3
import logging
from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource, abort, marshal_with, fields
from app.managers.device_group import (
    DeviceGroup,
    DeviceGroupUser,
    verify_users_used_same_device,
    is_member,
    is_owner,
    get_device_group,
    delete_device_group,
    update_device_group,
    get_device_groups_by_user,
    create_device_group,
    get_user_in_device_group,
    delete_user_in_device_group,
    update_user_in_device_group,
    get_users_in_device_group,
    add_user_to_device_group,
    register_user_face_in_device_group,
    auth_user_in_device_group,
    get_open_id_token,
    remove_user_face_from_device_group
)


errors = {
    'DeviceGroupNotFoundException': {
        'message': 'A device group with that groupId does not exist.',
        'status': 404,
    },
    'UserNotInDeviceGroupException': {
        'message': 'A user with that userId does not exist in a device group with that groupId.',
        'status': 404,
    },
    'UserAlreadyInDeviceGroupException': {
        'message': 'A user with that userId is already in a device group with that groupId.',
        'status': 409,
    },
    'NoFaceInImageException': {
        'message': 'There are no faces in the image. Should be at least 1.',
        'status': 404,
    },
    'FaceNotInDeviceGroupException': {
        'message': 'Could not find a user with that face in a device group with that groupId.',
        'status': 404,
    },
}


bp = Blueprint('groups', __name__)
api = Api(bp, errors=errors)


dynamodb = boto3.resource('dynamodb')

device_group_table = dynamodb.Table('MagicMirror-dev-device-group')
device_group_users_table = dynamodb.Table('MagicMirror-dev-device-group-users')


def get_cognito_user_id():
    # return request.environ['API_GATEWAY_AUTHORIZER']['claims']['sub']
    return request.environ['event']['requestContext']['identity']['cognitoIdentityId']


def abort_if_user_not_member_of_group(group_id):
    user_id = get_cognito_user_id()
    if not is_member(user_id, group_id):
        abort(403, message='User is not a member of that device group')


def abort_if_user_not_owner_of_group(group_id):
    user_id = get_cognito_user_id()
    if not is_owner(user_id, group_id):
        abort(403, message='User is not a owner of that device group')


device_group_fields = {
    'id': fields.String,
    'name': fields.String
}

device_group_user_fields = {
    'userId': fields.String(attribute='id'),
    'groupId': fields.String(attribute='group_id'),
    'owner': fields.String,
    'faceNum': fields.Integer(attribute='face_num')
}


class DeviceGroupApi(Resource):
    # Get a group - if user is a member (also PUT, DELETE)
    # GET /api/groups/:id
    @marshal_with(device_group_fields)
    def get(self, group_id):
        abort_if_user_not_member_of_group(group_id)
        group = get_device_group(group_id)
        return group

    def delete(self, group_id):
        # TODO delete member list?
        abort_if_user_not_owner_of_group(group_id)
        delete_device_group(group_id)
        return '', 204

    @marshal_with(device_group_fields)
    def put(self, group_id):
        abort_if_user_not_owner_of_group(group_id)
        data = request.get_json()
        group = DeviceGroup(group_id, data['name'])
        update_device_group(group)
        return group, 201


class DeviceGroupListApi(Resource):
    # Get list of groups - for which user is a member.. or owner???
    # GET /api/groups
    @marshal_with(device_group_fields)
    def get(self):
        owner = request.args.get('owner', False)
        user_id = get_cognito_user_id()
        groups = get_device_groups_by_user(user_id, owner)
        return groups

    # Create group - return new group and link (join user as owner)
    # POST /api/groups
    @marshal_with(device_group_fields)
    def post(self):
        data = request.get_json()
        group = create_device_group(data['name'])
        user_id = get_cognito_user_id()
        add_user_to_device_group(user_id, group.id, owner=True)
        return group, 201


api.add_resource(DeviceGroupApi, '/groups/<group_id>')
api.add_resource(DeviceGroupListApi, '/groups')


class DeviceGroupUserApi(Resource):
    # Get a user - check permission (also PUT, DELETE)
    # GET /api/groups/:id/users/:id
    @marshal_with(device_group_user_fields)
    def get(self, group_id, user_id):
        # TODO check permission
        cognito_user_id = get_cognito_user_id()
        if user_id != cognito_user_id and not is_owner(cognito_user_id):
            abort(403, message='User does not have permission to make changes to that user.')
        user = get_user_in_device_group(user_id, group_id)
        return user

    def delete(self, group_id, user_id):
        cognito_user_id = get_cognito_user_id()
        if user_id != cognito_user_id and not is_owner(cognito_user_id):
            abort(403, message='User does not have permission to make changes to that user.')
        delete_user_in_device_group(user_id, group_id)
        return '', 204

    # def put(self, group_id):
    #     # TODO check permission
    #     data = request.get_json()
    #     user = DeviceGroupUser(data['userid'], data['groupid'])
    #     update_user_in_device_group(user)
    #     return user, 201


class DeviceGroupUserListApi(Resource):
    # Get a list of users - check permission
    # GET /api/groups/:id/users/
    def get(self, group_id):
        abort_if_user_not_owner_of_group(group_id)
        users = get_users_in_device_group(group_id)
        return users

    # Add/join user to a group - return new user entry and link
    # POST /api/groups/:id/users
    def post(self, group_id):
        """Join a group/add a user to a device group
        """
        # data = request.get_json()
        user_id = get_cognito_user_id()

        # TODO test, check if device ids match
        owners = [user.id for user in get_users_in_device_group(group_id)
                  if user.owner]
        for owner in owners:
            if verify_users_used_same_device(user_id, owner):
                user = add_user_to_device_group(user_id, group_id, owner=False)
                return user, 201

        abort(403, 'Not permitted to join this group.')


api.add_resource(DeviceGroupUserApi, '/groups/<group_id>/users/<user_id>')
api.add_resource(DeviceGroupUserListApi, '/groups/<group_id>/users')


class DeviceGroupUserFacesApi(Resource):

    def post(self, group_id, user_id):
        # TODO check if in group??
        # if user_id != get_cognito_user_id():
        #     abort(403, message='User does not have permission to make changes to that user.')

        data = request.get_json()
        faces = data['faces']
        provider = data['provider']
        token = data['token']
        register_user_face_in_device_group(user_id, group_id, faces, provider, token)
        # TODO link account
        return '', 201

    def delete(self, group_id, user_id):
        cognito_user_id = get_cognito_user_id()
        if user_id != cognito_user_id and not is_owner(cognito_user_id):
            abort(403, message='User does not have permission to make changes to that user.')

        remove_user_face_from_device_group(user_id, group_id)
        return '', 204


api.add_resource(DeviceGroupUserFacesApi, '/groups/<group_id>/users/<user_id>/faces')


class DeviceGroupAuthApi(Resource):

    def post(self, group_id):
        # TODO check if in group??
        # if user_id != get_cognito_user_id():
        #     abort(403, message='User does not have permission to make changes to that user.')

        # obtain an identity ID and session token

        data = request.get_json()
        face = data['face']
        token = auth_user_in_device_group(group_id, face)
        return {'token': token}, 201


api.add_resource(DeviceGroupAuthApi, '/groups/<group_id>/auth')


class TokenApi(Resource):

    def post(self):
        data = request.get_json()
        provider = data['provider']
        token = data['token']
        user_id = get_cognito_user_id()
        token, identity_id = get_open_id_token(user_id, provider, token)
        return {'token': token, 'identityId': identity_id}


api.add_resource(TokenApi, '/openid/token')
