import os
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
