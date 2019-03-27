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
from curator.database import context
from threading import Thread, Event
import uuid
from curator.interfaces.vnv_components_interface import PlannerInterface, ExecutorInterface, PlatformAdapterInterface
from curator.interfaces.common_databases_interface import CatalogueInterface
from curator.interfaces.docker_interface import DockerInterface
from curator.worker import Worker
from curator.helpers import process_test_plan, cancel_test_plan, clean_environment
import time
from curator.logger import TangoLogger


# def process_test_plan(test_plan):
#     time.sleep(10)
#     app.logger.debug('completed ' + test_plan)
#     return 'completed'
app = Flask(__name__)
app.app_context()
RequestID(app)

# Setup logging
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s %(module)s.%(funcName)s "
                                       "[req_%(request_id)s] - %(message)s"))
handler.addFilter(RequestIDLogFilter())  # << Add request id contextual filter
logging.getLogger().addHandler(handler)

# _LOG = TangoLogger.getLogger('flask.app', log_level=logging.DEBUG, log_json=True)
# _LOG = logging.getLogger('flask.app')

API_ROOT = "api"
API_VERSION = "v1"

OK = 200
CREATED = 201
ACCEPTED = 202
BAD_REQUEST = 400
NOT_FOUND = 404
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
            'methods': ['GET', 'POST'],
            'path':'/'.join(['', API_ROOT, API_VERSION, 'test-preparations']),
            'description': 'Get current test plans or those running'
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
    return make_response(json.dumps(route_list), OK, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations']),
           methods=['GET', 'POST'])
def handle_new_test_plan():
    if request.method == 'GET':
        return make_response(
            json.dumps(context['test_preparations']),
            OK,
            {'Content-Type': 'application/json'}
        )
    elif request.method == 'POST':
        new_uuid = str(uuid.uuid4())  # Generate internal uuid ftm
        try:
            payload = request.get_json()
            app.logger.debug(f'Received JSON: {payload}')
            # _LOG.debug(f'Received JSON: {payload}')
            # required_keys = {'test_descriptor', 'network_service_descriptor', 'paths'}
            # if payload.keys() is not None and all(key in payload.keys() for key in required_keys):
            context['test_preparations'][new_uuid] = payload  # Should have
            process_thread = Thread(target=process_test_plan, args=(new_uuid,))
            process_thread.start()
            context['threads'].append(process_thread)
            return make_response(json.dumps({'test-plan-uuid': new_uuid, 'status': 'STARTING'}), CREATED, {'Content-Type': 'application/json'})
            # else:
            #     return make_response(
            #         json.dumps({'error': 'Keys {} required in payload'.format(required_keys)}),
            #         BAD_REQUEST,
            #         {'Content-Type': 'application/json'}
            #     )
        except Exception as e:
            return make_response(json.dumps({'exception': e}), INTERNAL_ERROR, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>']),
           methods=['DELETE'])
def test_plan_cancelled(test_bundle_uuid):
    app.logger.debug(f'Canceling test_plan ')
    # _LOG.debug(f'Canceling test_plan ')
    process_thread = Thread(target=cancel_test_plan, args=(request.get_json(), test_bundle_uuid))
    process_thread.start()
    return make_response('{"error": null}', ACCEPTED, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations','<test_bundle_uuid>', 'service-instances',
                     '<instance_name>','sp-ready']),
           methods=['POST'])
def prepare_environment_callback(test_bundle_uuid, instance_name):
    """
    This callback is used by OSM to notify
    :param test_bundle_uuid:
    :param instance_name:
    :return:
    """
    # Notify SP setup blocked thread
    try:
        payload = request.get_json()
        # _LOG.debug(f'Callback received, contains {payload}')
        app.logger.debug(f'Callback received, contains {payload}')
        required_keys = {'ns_instance_uuid', 'functions', 'platform_type'}
        if all(key in payload.keys() for key in required_keys):
            # FIXME: Check which entry contains the corresponding type of platform (with nsi_name)
            # FIXME: or ask it in the callback
            context['test_preparations'][test_bundle_uuid]['augmented_descriptors'].append(
                {
                    'nsi_uuid': payload['ns_instance_uuid'],
                    # 'nsi_name': payload['instance_name'],
                    'platform': payload['platform_type'],
                    'functions': payload['functions']
                }
            )
            context['events'][test_bundle_uuid][instance_name].set()  # Unlocks thread
            return make_response('{"error": null}', OK,{'Content-Type': 'application/json'})
        else:
            # TODO abort test, reason nsi
            return make_response(
                json.dumps({'error': 'Keys {required_keys} required in payload'}),
                BAD_REQUEST,
                {'Content-Type': 'application/json'}
            )
    except Exception as e:
        return make_response(json.dumps({'exception': e}), INTERNAL_ERROR, {'Content-Type': 'application/json'})


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
        executor_payload = request.get_json()
        test_index = next(
            (index for (index, d) in
                enumerate(context['test_preparations'][test_bundle_uuid]['augmented_descriptors'])
                if d['test_uuid'] == executor_payload['test-uuid']), None)
        (context['test_preparations'][test_bundle_uuid]['augmented_descriptors']
            [test_index]['status']) = executor_payload['status']
        return make_response('{}', OK, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'exception': e}), INTERNAL_ERROR, {'Content-Type': 'application/json'})


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'tests', '<test_uuid>', 'finish']),
    methods=['POST'])
def test_finished(test_bundle_uuid, test_uuid):
    process_thread = Thread(target=clean_environment, args=(test_bundle_uuid, test_uuid, request.get_json(),))
    return make_response('{"error": null}', OK, {'Content-Type': 'application/json'})


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_bundle_uuid>', 'tests', '<test_uuid>', 'cancel']),
    methods=['POST'])
def test_cancelled(test_bundle_uuid, test_uuid):
    # Wrap up, notify
    payload = request.get_json()
    context['test_preparations'][test_bundle_uuid]['test_results'].append(payload)
    context['events'][test_bundle_uuid][test_uuid].set()
    return make_response('{"error": null}', OK, {'Content-Type': 'application/json'})


#  Future
# @app.route('/'.join(
#     ['', API_ROOT, API_VERSION, 'test-management', 'probes', 'prune']),
#     methods=['POST'])
# def clean_probe_inventory():
#     # Require login:password
#     return make_response('', OK)


#  Utils

@app.errorhandler(NOT_FOUND)
def not_found(error):
    return make_response(json.dumps({'code': '404 Not Found', 'message': error.description}),
                         NOT_FOUND, {'Content-Type': 'application/json'})


@app.after_request
def after_request(response):
    app.logger.info(f'{request.remote_addr} {request.scheme} {request.method}'
    # _LOG.info(f'{request.remote_addr} {request.scheme} {request.method}'
                    f' {request.full_path} {response.status} {response.content_length}')
    response.headers.add('X-REQUEST-ID', current_request_id())
    return response


def main():
    context['alive_since'] = datetime.utcnow().replace(microsecond=0)
    context['test_preparations'] = {}
    context['host'] = 'tng-vnv-curator:6200'
    padapt_iface = PlatformAdapterInterface(API_ROOT, API_VERSION)
    exec_iface = ExecutorInterface(API_ROOT, API_VERSION)
    plan_iface = PlannerInterface(API_ROOT, API_VERSION)
    cat_iface = CatalogueInterface()
    docker_iface = DockerInterface()
    context['plugins'] = {
        'platform_adapter': padapt_iface,
        'executor': exec_iface,
        'planner': plan_iface,
        'catalogue': cat_iface,
        'docker': docker_iface
    }
    context['events'] = {}
    context['threads'] = []
    app.run(debug=True, host='0.0.0.0', port=context['host'].split(':')[1], threaded=True)


if __name__ == "__main__":
    main()
