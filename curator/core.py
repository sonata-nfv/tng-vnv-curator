# Copyright (c) 2019 5GTANGO
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, 5GTANGO
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
#
# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).


from flask import Flask, session, request, Response, json, url_for, make_response, g
import requests
from datetime import datetime
from database import context
from threading import Thread
import uuid
from worker import Worker
import time
from helpers import *


# def process_test_plan(test_plan):
#     time.sleep(10)
#     app.logger.debug('completed ' + test_plan)
#     return 'completed'


app = Flask(__name__)

app.app_context()

API_ROOT = "api"
API_VERSION = "v1"


@app.route('/')
def home():
    return make_response("<h1>5GTango VnV Curator</h1>")


@app.route('/ping')
def ping():
    return make_response(
        json.dumps({'alive_since': '{}Z'.format(context['alive_since'].isoformat())}),
        {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION]))
def list_routes():
    route_list = [
        {
            'methods': ['GET'],
            'path': '/ping',
            'description': ''
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations']),
            'description': ''
        },
        {
            'methods': ['DELETE'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>']),
            'description': ''
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change']),
            'description': ''
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change',
                             '<test_uuid>', 'finish']),
            'description': ''
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change',
                             '<test_uuid>', 'cancel']),
            'description': ''
        },
    ]
    return make_response(json.dumps(route_list), 200, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations']), methods=['POST'])
def handle_new_test_plan():
    new_uuid = str(uuid.uuid4())
    process_thread = Thread(target=process_test_plan, args=(app, request.get_json(), new_uuid))
    process_thread.start()
    return make_response(new_uuid, 201)


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>']), methods=['DELETE'])
def test_plan_cancelled(test_bundle_uuid):
    process_thread = Thread(target=cancel_test_plan, args=(app, request.get_json(), test_bundle_uuid))
    process_thread.start()
    return make_response('', 202)


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change']),
           methods=['POST'])
def test_in_execution(test_bundle_uuid):
    new_uuid = str(uuid.uuid4())
    return make_response(new_uuid, 200)


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change', '<test_uuid>', 'finish']),
    methods=['POST'])
def test_finished(test_bundle_uuid, test_uuid):
    # Wrap up
    return make_response(200)


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change', '<test_uuid>', 'cancel']),
    methods=['POST'])
def test_cancelled(test_bundle_uuid, test_uuid):
    # Wrap up, notify
    return make_response('', 200)


if __name__ == "__main__":
    context['alive_since'] = datetime.utcnow().replace(microsecond=0)
    context['test-preparations'] = {}
    app.run(debug=True, port=6101, threaded=True)
