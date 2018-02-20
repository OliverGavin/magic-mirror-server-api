from flask import Flask
from flask import request, jsonify

from app.api.device_group import device_group_bp


app = Flask(__name__)
app.register_blueprint(device_group_bp, url_prefix='/api')


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


@app.route("/")
def hello():
    return jsonify(request.environ['API_GATEWAY_AUTHORIZER'])


# request.environ['API_GATEWAY_AUTHORIZER'] = {
#   "claims": {
#     "aud": "1ttl3ir4v456e9ari3eqgbjsge",
#     "auth_time": "1518532281",
#     "cognito:username": "t@t.com",
#     "event_id": "5c1c86eb-0d2e-11e8-b0a3-754c029ec344",
#     "exp": "Tue Feb 13 15:31:21 UTC 2018",
#     "iat": "Tue Feb 13 14:31:21 UTC 2018",
#     "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_PtJ4NoVML",
#     "name": "Tester",
#     "sub": "d0e83481-dfb1-4bcb-acbe-b75610e92021",
#     "token_use": "id"
#   }
# }




# API_GATEWAY_AUTHORIZER
# HTTP_AUTHORIZATION
# event
# context
