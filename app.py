from flask import Flask
from flask import request, jsonify
app = Flask(__name__)


@app.route("/")
def hello():
    return jsonify(list(request.environ['API_GATEWAY_AUTHORIZER']))


# API_GATEWAY_AUTHORIZER
# HTTP_AUTHORIZATION
# event
# context
