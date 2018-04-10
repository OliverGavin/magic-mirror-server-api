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
    return request.environ['event']['requestContext']['identity']['cognitoIdentityId']


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

    @marshal_with(integrations_fields)
    def get(self):
        integrations = get_integrations()
        return integrations


api.add_resource(IntegrationListApi, '/integrations')
