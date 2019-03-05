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
from flask_log_request_id import RequestID, current_request_id, RequestIDLogFilter
import logging.config
import logging
import requests
from datetime import datetime
from time import strftime
from database import context
from threading import Thread
import uuid
from interfaces import CatalogueClient, PlannerClient, PlatformAdapterClient, ExecutorClient
from worker import Worker
from helpers import process_test_plan, cancel_test_plan
import time


# def process_test_plan(test_plan):
#     time.sleep(10)
#     app.logger.debug('completed ' + test_plan)
#     return 'completed'
app = Flask(__name__)
app.app_context()
RequestID(app)

# Setup logging
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(module)s.%(funcName)s [req_%(request_id)s] - %(message)s"))
handler.addFilter(RequestIDLogFilter())  # << Add request id contextual filter
logging.getLogger().addHandler(handler)


API_ROOT = "api"
API_VERSION = "v1"

OK = 200
CREATED = 201
ACCEPTED = 202
INTERNAL_ERROR = 500


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
            'description': 'Module sanity check'
        },
        {
            'methods': ['GET'],
            'path': '/'.join(['', API_ROOT, API_VERSION]),
            'description': 'This api reference'
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations']),
            'description': 'Create a new test preparation'
        },
        {
            'methods': ['DELETE'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>']),
            'description': 'Cancel a test preparation'
        },
        {
            'methods': ['POST'],
            'path': '/'.join(['', API_ROOT, API_VERSION, 'test-preparations','<test_bundle_uuid>', 'sp-ready']),
            'description': 'Callback for Platform Adapter to notify when a Network Service has been instantiated '
                           'in OSM platform successfully'
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change']),
            'description': 'Callback for Executor to notify running tests'
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'tests',
                             '<test_uuid>', 'finish']),
            'description': 'Callback for Executor to notify when a test has finished successfully'
        },
        {
            'methods': ['POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'tests',
                             '<test_uuid>', 'cancel']),
            'description': 'Callback for Executor to notify when a test has finished due '
                           'to an error or has been cancelled'
        },
    ]
    return make_response(json.dumps(route_list), 200, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations']),
           methods=['POST'])
def handle_new_test_plan():
    new_uuid = str(uuid.uuid4())
    try:
        context['test_preparations'][new_uuid] = {'test_plan': request.get_json()}
        process_thread = Thread(target=process_test_plan, args=(app, context['test_preparations'][new_uuid], new_uuid))
        process_thread.start()
        return make_response(new_uuid, CREATED)
    except Exception as e:
        return make_response(e, INTERNAL_ERROR)


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>']),
           methods=['DELETE'])
def test_plan_cancelled(test_bundle_uuid):
    app.logger.debug('Hello')
    process_thread = Thread(target=cancel_test_plan, args=(app, request.get_json(), test_bundle_uuid))
    process_thread.start()
    return make_response('', ACCEPTED)


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations','<test_bundle_uuid>', 'sp-ready']),
           methods=['POST'])
def prepare_environment_callback(test_bundle_uuid):
    """
    This callback is used by OSM to notify
    :param test_bundle_uuid:
    :return:
    """
    # Notify SP setup blocked thread
    return make_response('', OK)


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'change']),
           methods=['POST'])
def test_in_execution(test_bundle_uuid):
    """
    Executor->Curator
    Test in execution: executor responses with the Test ID that can be used in a future test cancellation
    { "test-id": <test_id> }(?)
    :param test_bundle_uuid:
    :return:
    """
    try:
        context['test_preparations'][test_bundle_uuid]['test_instances_running'].append(request.get_json()['test_id'])
        return make_response('', OK)
    except:
        return make_response('', INTERNAL_ERROR)


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'tests', '<test_uuid>', 'finish']),
    methods=['POST'])
def test_finished(test_bundle_uuid, test_uuid):
    # Wrap up
    return make_response('', OK)


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'tests', '<test_uuid>', 'cancel']),
    methods=['POST'])
def test_cancelled(test_bundle_uuid, test_uuid):
    # Wrap up, notify
    return make_response('', OK)


#  Future
# @app.route('/'.join(
#     ['', API_ROOT, API_VERSION, 'test-management', 'probes', 'prune']),
#     methods=['POST'])
# def clean_probe_inventory():
#     # Require login:password
#     return make_response('', OK)


#  Utils

@app.errorhandler(404)
def not_found(error):
    return make_response(json.dumps({'code': '404 Not Found','message': error.description}),
                         404, {'Content-Type': 'application/json'})


@app.after_request
def after_request(response):
    app.logger.info('{} {} {} {} {} {}'.format(
        request.remote_addr,
        request.scheme,
        request.method,
        request.full_path,
        response.status,
        response.content_length
    ))
    response.headers.add('X-REQUEST-ID', current_request_id())
    return response


def main():
    context['alive_since'] = datetime.utcnow().replace(microsecond=0)
    context['test_preparations'] = {}
    context['host_port'] = 'tng-vnv-curator:6101'
    app.run(debug=True, port=context['host_port'].split(':')[1], threaded=True)


if __name__ == "__main__":
    main()
