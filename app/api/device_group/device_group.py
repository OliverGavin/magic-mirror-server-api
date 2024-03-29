import boto3
import logging
from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource, abort, marshal_with, fields
from app.managers.device_group import (
    DeviceGroup,
    DeviceGroupUser,
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


def get_cognito_user_id():
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
    # Get list of groups - for which user is a member
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


class DeviceGroupUserListApi(Resource):
    # Get a list of users - check permission
    # GET /api/groups/:id/users/
    def get(self, group_id):
        abort_if_user_not_owner_of_group(group_id)
        users = get_users_in_device_group(group_id)
        return users

    # Add/join user to a group - return new user entry and link
    # POST /api/groups/:id/users
    @marshal_with(device_group_user_fields)
    def post(self, group_id):
        """Join a group/add a user to a device group
        """
        data = request.get_json()
        user_id = get_cognito_user_id()

        if user_id != data['userId']:
            abort(403, 'Not permitted to join this group.')

        user = add_user_to_device_group(user_id, group_id, owner=False)
        return user, 201


api.add_resource(DeviceGroupUserApi, '/groups/<group_id>/users/<user_id>')
api.add_resource(DeviceGroupUserListApi, '/groups/<group_id>/users')


class DeviceGroupUserFacesApi(Resource):

    def post(self, group_id, user_id):
        data = request.get_json()
        faces = data['faces']
        provider = data['provider']
        token = data['token']
        face_num = register_user_face_in_device_group(user_id, group_id, faces, provider, token)
        if face_num < 3:
            abort(403, message='There are no faces in the image. Should be at least 1.')
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
        data = request.get_json()
        face = data['face']
        token, identity_id = auth_user_in_device_group(group_id, face)
        return {'token': token, 'identityId': identity_id}, 201


api.add_resource(DeviceGroupAuthApi, '/groups/<group_id>/auth')
