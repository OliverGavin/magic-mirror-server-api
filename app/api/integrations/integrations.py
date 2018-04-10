import logging
from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource, abort, marshal_with, fields
from app.managers.integrations import (
    Integration,
    get_integrations
)


errors = {
    'IntegrationNotFoundException': {
        'message': 'An integration with that integrationId does not exist.',
        'status': 404,
    }
}


bp = Blueprint('integrations', __name__)
api = Api(bp, errors=errors)


def get_cognito_user_id():
    # return request.environ['API_GATEWAY_AUTHORIZER']['claims']['sub']
    return request.environ['event']['requestContext']['identity']['cognitoIdentityId']


# def abort_if_user_not_member_of_group(group_id):
#     user_id = get_cognito_user_id()
#     if not is_member(user_id, group_id):
#         abort(403, message='User is not a member of that device group')


device_group_user_integrations_fields = {
    'userId': fields.String(attribute='id'),
    'groupId': fields.String(attribute='group_id'),
    'integrationId': fields.String(attribute='integration_id'),
    'position': fields.Integer
}

integrations_fields = {
    'integrationId': fields.String(attribute='integration_id'),
    'functionName': fields.Integer(attribute='function_name')
}


class IntegrationListApi(Resource):
    # Get list of groups - for which user is a member.. or owner???
    # GET /api/groups
    @marshal_with(integrations_fields)
    def get(self):
        integrations = get_integrations()
        return integrations


api.add_resource(IntegrationListApi, '/integrations')


# class DeviceGroupUserIntegrationsApi(Resource):
#     # Get a user - check permission (also PUT, DELETE)
#     # GET /api/groups/:id/users/:id
#     @marshal_with(device_group_user_fields)
#     def get(self, group_id, user_id, integration_id):
#         # TODO check permission
#         cognito_user_id = get_cognito_user_id()
#         if user_id != cognito_user_id and not is_owner(cognito_user_id):
#             abort(403, message='User does not have permission to make changes to that user.')
#         user = get_user_in_device_group(user_id, group_id)
#         return user
#
#     def delete(self, group_id, user_id, integration_id):
#         cognito_user_id = get_cognito_user_id()
#         if user_id != cognito_user_id and not is_owner(cognito_user_id):
#             abort(403, message='User does not have permission to make changes to that user.')
#         delete_user_in_device_group(user_id, group_id)
#         return '', 204
#
#     # def put(self, group_id):
#     #     # TODO check permission
#     #     data = request.get_json()
#     #     user = DeviceGroupUser(data['userid'], data['groupid'])
#     #     update_user_in_device_group(user)
#     #     return user, 201
#
#
# class DeviceGroupUserIntegrationsListApi(Resource):
#     # Get a list of users - check permission
#     # GET /api/groups/:id/users/
#     def get(self, group_id, user_id):
#         abort_if_user_not_member_of_group(group_id)
#         users = get_users_in_device_group(group_id)
#         return users
#
#     # Add/join user to a group - return new user entry and link
#     # POST /api/groups/:id/users
#     @marshal_with(device_group_user_fields)
#     def post(self, group_id, user_id):
#         """Join a group/add a user to a device group
#         """
#         data = request.get_json()
#         user_id = get_cognito_user_id()
#
#         if user_id != data['userId']:
#             abort(403, 'Not permitted to join this group.')
#
#         user = add_user_to_device_group(user_id, group_id, owner=False)
#         return user, 201
#
#
# api.add_resource(DeviceGroupUserIntegrationsApi, '/groups/<group_id>/users/<user_id>/integrations/<integration_id>')
# api.add_resource(DeviceGroupUserIntegrationsListApi, '/groups/<group_id>/users/<user_id>/integrations')
