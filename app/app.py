import os
from flask import Flask
from flask import request, jsonify

from app.api.device_group import device_group_bp


app = Flask(__name__)
app.register_blueprint(device_group_bp, url_prefix='/api')


# if os.environ['IS_OFFLINE']:
#     @app.before_request
#     def before_request():
#         request.environ['API_GATEWAY_AUTHORIZER'] = {
#           "claims": {
#             "aud": "1ttl3ir4v456e9ari3eqgbjsge",
#             "auth_time": "1518532281",
#             "cognito:username": "t@t.com",
#             "event_id": "5c1c86eb-0d2e-11e8-b0a3-754c029ec344",
#             "exp": "Tue Feb 13 15:31:21 UTC 2018",
#             "iat": "Tue Feb 13 14:31:21 UTC 2018",
#             "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_PtJ4NoVML",
#             "name": "Tester",
#             "sub": "d0e83481-dfb1-4bcb-acbe-b75610e92021",
#             "token_use": "id"
#           }
#         }


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route("/test/request-context")
def test3():
    return jsonify(request.environ['event']['requestContext'])


# requestContext:
#     accountId:"834819762693"
#     apiId:"edhvqd74g0"
#     httpMethod:"GET"
#     identity:
#         accessKey:"ASIAJEH3TOGRBDXFW6DA"
#         accountId:"834819762693"
#         caller:"AROAJGNHAWNRPRN6G4CBU:CognitoIdentityCredentials"
#         cognitoAuthenticationProvider:"graph.facebook.com,graph.facebook.com:1634271429961880:1810025299029282"
#         cognitoAuthenticationType:"authenticated"
#         cognitoIdentityId:"eu-west-1:58607b5f-b0e3-42c6-9321-bc83176866bb"
#         cognitoIdentityPoolId:"eu-west-1:ec035e01-6226-4cb2-88f1-9cf348916d72"
#         sourceIp:"185.51.72.15"
#         user:"AROAJGNHAWNRPRN6G4CBU:CognitoIdentityCredentials"
#         userAgent:"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) electron_app/1.0.0 Chrome/58.0.3029.110 Electron/1.7.10 Safari/537.36"
#         userArn:"arn:aws:sts::834819762693:assumed-role/MagicMirror-dev-CognitoAuthorizedRole-B0K4LUDRU6Y3/CognitoIdentityCredentials"


# API_GATEWAY_AUTHORIZER
# HTTP_AUTHORIZATION
# event
# context
