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
# from flask_log_request_id import RequestID, current_request_id, RequestIDLogFilter
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
from curator.helpers import process_test_plan, cancel_test_plan, clean_environment
import time
from curator.logger import TangoLogger
import traceback


# def process_test_plan(test_plan):
#     time.sleep(10)
#     app.logger.debug('completed ' + test_plan)
#     return 'completed'
app = Flask(__name__)
# app.app_context()
# RequestID(app)

# Setup logging
# handler = logging.StreamHandler()
# handler.setFormatter(logging.Formatter("[%(asctime)s] %(name)s %(levelname)s %(module)s.%(funcName)s "
#                                        "[req_%(request_id)s] - %(message)s"))
# handler.addFilter(RequestIDLogFilter())  # << Add request id contextual filter
# logging.getLogger().addHandler(handler)

_LOG = TangoLogger.getLogger('curator:core', log_level=logging.DEBUG, log_json=True)
# _LOG = logging.getLogger('flask.app')

API_ROOT = "api"
API_VERSION = "v1"

OK = 200
CREATED = 201
ACCEPTED = 202
BAD_REQUEST = 400
NOT_FOUND = 404
NOT_ACCEPTABLE = 406
INTERNAL_ERROR = 500


@app.route('/')
def home():
    return make_response('{"module": "5GTango VnV Curator", "status": "RUNNING"}', {'Content-Type': 'application/json'})


@app.route('/ping')
def ping():
    return make_response(
        json.dumps({'alive_since': '{}Z'.format(context['alive_since'].isoformat())}),
        {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION]))
def list_routes():
    route_list = app.url_map.iter_rules()
    description_ref = {
        'ping': 'Module sanity check',
        'handle_new_test_plan': 'Get current test plans running or launch a new one',
        'dummy_endpoint': 'Endpoint for debugging',
        'get_context': 'Get current state of the module',
        'list_routes': 'This api reference',
        'home': 'home',
        'prepare_environment_callback': 'Callback to allow Platform Adapter to notify the Curator that '
                                        '<instance_name> instantiation finished',
        'test_finished': 'Callback to allow Executor to notify the Curator that '
                                        '<test_uuid> execution finished',
        'test_cancelled': 'Callback to allow Executor to notify the Curator that <test_uuid> cancellation finished,'
                          ' or that there was an error during cancellation or execution',
        'test_in_execution': 'Callback to allow Executor to notify the Curator that a test is running',
        'test_plan_cancelled': 'Callback to allow Planner to cancel a running Test Plan'
    }
    route_output = [
        {
            'methods': list(rule.methods), 'path': rule.rule,
            'description': description_ref[rule.endpoint] if rule.endpoint in description_ref.keys() else ''
        } for rule in route_list if rule.endpoint != 'static'
    ]
    return make_response(json.dumps(route_output), OK, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations']),
           methods=['GET', 'POST'])
def handle_new_test_plan():
    """
    'nsd_uuid', 'testd_uuid', 'last_test', 'test_plan_callbacks' keys are
    mandatory, but if included, but nsd and testd can be overriden if 'nsd'
    and/or 'testd' are included.
    :return:
    """
    if request.method == 'GET':
        return make_response(
            json.dumps(context['test_preparations']),
            OK,
            {'Content-Type': 'application/json'}
        )
    elif request.method == 'POST':
        # app.logger.debug(f'New test plan received, contains {request.get_data()}, '
        #                  f'Content-type: {request.headers["Content-type"]}')
        _LOG.debug(f'New test plan received, contains {request.get_data()}, '
                         f'Content-type: {request.headers["Content-type"]}')
        if request.headers["Content-type"].split(';')[0] != 'application/json':
            return make_response(json.dumps({'exception': 'A valid JSON payload is required', 'status': 'ERROR'}), NOT_ACCEPTABLE,
                                 {'Content-Type': 'application/json'})
        # required_keys = {'nsd', 'testd', 'last_test', 'test_plan_callbacks'}
        # required_keys = {'nsd_uuid', 'testd_uuid', 'last_test', 'test_plan_callbacks'}
        required_keys = {'nsd_uuid', 'testd_uuid', 'test_plan_callbacks'}
        try:
            payload = request.get_json()
            # app.logger.debug(f'Received JSON: {payload}')
            _LOG.debug(f'Received JSON: {payload}')
            if all(key in payload.keys() for key in required_keys):
                missing_content_msg = 'Missing '
                missing_content_msg_len = len(missing_content_msg)
                if 'test_plan_uuid' not in payload.keys():
                    new_uuid = str(uuid.uuid4())  # Generate internal uuid ftm
                    # app.logger.warning(f'There was no test_plan_uuid in payload, generated #{new_uuid}')
                    _LOG.warning(f'There was no test_plan_uuid in payload, generated #{new_uuid}')
                else:
                    new_uuid = payload['test_plan_uuid']
                    # app.logger.debug(f'Received new test plan #{new_uuid}')
                    _LOG.debug(f'Received new test plan #{new_uuid}')
                for key in required_keys:
                    if payload[key] is None:
                        missing_content_msg += f'{key} content, '
                if missing_content_msg_len < len(missing_content_msg):
                    return make_response(
                        json.dumps({'exception': missing_content_msg[:-2], 'status': 'ERROR'}),
                        BAD_REQUEST,
                        {'Content-Type': 'application/json'})
                else:
                    del missing_content_msg_len, missing_content_msg

                # _LOG.debug(f'Received JSON: {payload}')
                # required_keys = {'test_descriptor', 'network_service_descriptor', 'paths'}
                # if payload.keys() is not None and all(key in payload.keys() for key in required_keys):
                if new_uuid not in context['test_preparations']:
                    context['test_preparations'][new_uuid] = payload  # Should have
                else:
                    msg = f'test-plan ({new_uuid}) exists, aborting'
                    # app.logger.error(msg)
                    _LOG.error(msg)
                    return make_response(
                        json.dumps({'exception': msg, 'status': 'ERROR'}),
                        BAD_REQUEST,
                        {'Content-Type': 'application/json'})
                create_time = datetime.utcnow().replace(microsecond=0)
                context['test_preparations'][new_uuid]['created_at'] = create_time
                context['test_preparations'][new_uuid]['updated_at'] = create_time
                process_thread = Thread(target=process_test_plan, args=(new_uuid,))
                process_thread.start()
                context['threads'].append(process_thread)
                return make_response(json.dumps({'test_plan_uuid': new_uuid, 'status': 'STARTING'}),
                                     CREATED, {'Content-Type': 'application/json'})
                # else:
                #     return make_response(
                #         json.dumps({'error': 'Keys {} required in payload'.format(required_keys)}),
                #         BAD_REQUEST,
                #         {'Content-Type': 'application/json'}
                #     )
            else:
                return make_response(json.dumps({'exception': f'Missing keys, mandatory fields are {required_keys}', 'status': 'ERROR'}),
                                     NOT_ACCEPTABLE,
                                     {'Content-Type': 'application/json'})
        except Exception as e:
            return make_response(json.dumps({'exception': e, 'status': 'ERROR'}), INTERNAL_ERROR, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_plan_uuid>']),
           methods=['GET', 'DELETE'])
def test_plan_cancelled(test_plan_uuid):
    if request.method == 'GET':
        # single test_plan status
        # TODO: Update function name and description to avoid misunderstanding
        return make_response(
            json.dumps(context['test_preparations'][test_plan_uuid]),
            OK,
            {'Content-Type': 'application/json'}
        )
    elif request.method == 'DELETE':
        _LOG.debug(f'Cancelling test_plan {test_plan_uuid}')
        # app.logger.debug(f'Cancelling test_plan {test_plan_uuid}')
        if test_plan_uuid not in context['test_preparations']:
            return make_response(
                '{"exception":"Test-plan requested for cancellation is not currently executing", "status":"ERROR"}',
                NOT_FOUND,
                {'Content-Type': 'application/json'}
            )
        context['test_preparations'][test_plan_uuid]['updated_at'] = datetime.utcnow().replace(microsecond=0)
        process_thread = Thread(target=cancel_test_plan, args=(test_plan_uuid, ))
        process_thread.start()
        context['threads'].append(process_thread)
        return make_response('{"error": null, "status": "CANCELLING"}', ACCEPTED, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations','<test_plan_uuid>', 'service-instances',
                     '<instance_name>', 'sp-ready']),
           methods=['POST'])
def prepare_environment_callback(test_plan_uuid, instance_name):
    """This callback is used by PA to notify the result of an instantiation and continue with
    the testing schedule
    :param test_plan_uuid:
    :param instance_name:
    :return:
    """
    # Notify SP setup blocked thread
    # app.logger.debug(f'Callback received {request.path}, contains {request.get_data()}, '
    #                  f'Content-type: {request.headers["Content-type"]}')
    _LOG.debug(f'Callback received {request.path}, contains {request.get_data()},'
               f'Content-type: {request.headers["Content-type"]}')
    try:
        payload = request.get_json()
        if not context['test_preparations'].get(test_plan_uuid):
            make_response(
                f'{{"error": "Test plan #{test_plan_uuid} has been cancelled or was not found"}}',
                NOT_FOUND,
                {'Content-Type': 'application/json'}
            )

        context['test_preparations'][test_plan_uuid]['updated_at'] = datetime.utcnow().replace(microsecond=0)
        # payload = json.loads(request.get_data().decode("UTF-8"))
        _LOG.debug(f'Callback received, contains {payload}')
        # app.logger.debug(f'Callback received, contains {payload}')
        required_keys = {'ns_instance_uuid', 'functions', 'platform_type'}
        if all(key in payload.keys() for key in required_keys) and 'error' not in payload.keys():
            # FIXME: Check which entry contains the corresponding type of platform (with nsi_name)
            # FIXME: or ask it in the callback
            context['test_preparations'][test_plan_uuid]['augmented_descriptors'].append(
                {
                    'nsi_uuid': payload['ns_instance_uuid'],
                    'nsi_name': instance_name,
                    'functions': payload['functions'],
                    'platform': {'platform_type': payload['platform_type']},
                    'error': None
                }
            )
            context['events'][test_plan_uuid][instance_name].set()  # Unlocks thread
            return make_response('{"error": null}', OK,{'Content-Type': 'application/json'})
        elif 'error' in payload.keys():
            context['test_preparations'][test_plan_uuid]['augmented_descriptors'].append(
                {
                    'nsi_uuid': None,
                    'platform': {'platform_type': 'unknown'},
                    'functions': None,
                    'nsi_name': instance_name,
                    'error': payload['error']
                }
            )
            context['events'][test_plan_uuid][instance_name].set()
            return make_response('{"error": null}', OK, {'Content-Type': 'application/json'})
        else:
            # TODO abort test, reason nsi
            context['test_preparations'][test_plan_uuid]['augmented_descriptors'].append(
                {
                    'nsi_uuid': None,
                    'platform': {'platform_type': 'unknown'},
                    'functions': None,
                    'nsi_name': instance_name,
                    'error': 'Unknown error'
                }
            )
            context['events'][test_plan_uuid][instance_name].set()
            return make_response(
                json.dumps({'error': 'Keys {required_keys} required in payload'}),
                BAD_REQUEST,
                {'Content-Type': 'application/json'}
            )
    except Exception as e:
        _LOG.error(f'Got an Exception: {e}')
        return make_response(json.dumps({'exception': e.args}), INTERNAL_ERROR, {'Content-Type': 'application/json'})


@app.route('/'.join(['', API_ROOT, API_VERSION, 'test-preparations', '<test_plan_uuid>', 'change']),
           methods=['POST'])
def test_in_execution(test_plan_uuid):
    """
    Executor->Curator
    Test in execution: executor responses with the Test ID that can be used in a future test cancellation
    { "test-id": <test_id> }(?)
    :param test_plan_uuid:
    :return:
    """
    # app.logger.debug(f'Callback received {request.path}, contains {request.get_data()}, '
    #                  f'Content-type: {request.headers["Content-type"]}')
    _LOG.debug(f'Callback received {request.path}, contains {request.get_data()}, '
                     f'Content-type: {request.headers["Content-type"]}')
    try:
        executor_payload = request.get_json()
        context['test_preparations'][test_plan_uuid]['updated_at'] = datetime.utcnow().replace(microsecond=0)
        test_index = next(
            (index for (index, d) in
                enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
                if d['test_uuid'] == executor_payload['test_uuid']), None)
        (context['test_preparations'][test_plan_uuid]['augmented_descriptors']
            [test_index]['test_status']) = executor_payload['status'] if 'status' in executor_payload.keys() \
            else 'RUNNING'
        return make_response('{}', OK, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'exception': e.args}), INTERNAL_ERROR, {'Content-Type': 'application/json'})


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_plan_uuid>', 'tests', '<test_uuid>', 'finish']),
    methods=['POST'])
def test_finished(test_plan_uuid, test_uuid):
    try:
        # app.logger.debug(f'Callback received {request.path}, contains {request.get_data()}, '
        #                  f'Content-type: {request.headers["Content-type"]}')
        _LOG.debug(f'Callback received {request.path}, contains {request.get_data()}, '
                         f'Content-type: {request.headers["Content-type"]}')
        context['test_preparations'][test_plan_uuid]['updated_at'] = datetime.utcnow().replace(microsecond=0)
        process_thread = Thread(target=clean_environment, args=(test_plan_uuid, test_uuid, request.get_json(),))
        process_thread.start()
        context['threads'].append(process_thread)
    except Exception as e:
        tb = "".join(traceback.format_exc().split("\n"))
        # app.logger.error(f'Error in test_finished callback: {tb}')
        _LOG.error(f'Error in test_finished callback: {tb}')
        return make_response(json.dumps({'error': tb}), INTERNAL_ERROR, {'Content-Type': 'application/json'})
    return make_response('{"error": null}', OK, {'Content-Type': 'application/json'})


@app.route('/'.join(
    ['', API_ROOT, API_VERSION, 'test-preparations', '<test_plan_uuid>', 'tests', '<test_uuid>', 'cancel']),
    methods=['POST'])
def test_cancelled(test_plan_uuid, test_uuid):
    # Wrap up, notify
    # app.logger.debug(f'Callback received {request.path}, contains {request.get_data()}, '
    #                  f'Content-type: {request.headers["Content-type"]}')
    _LOG.debug(f'Callback received {request.path}, contains {request.get_data()}, '
                     f'Content-type: {request.headers["Content-type"]}')
    try:
        payload = request.get_json()
        if test_plan_uuid not in context['test_preparations']:
            return make_response(
                '{"exception":"Test-plan requested for cancellation is not currently executing", "status":"ERROR"}',
                NOT_FOUND,
                {'Content-Type': 'application/json'}
            )
        context['test_preparations'][test_plan_uuid]['updated_at'] = datetime.utcnow().replace(microsecond=0)
        if payload['status'] != 'ERROR':
            # app.logger.debug(f'Test #{test_uuid} cancellation was correct on executor')
            _LOG.debug(f'Test #{test_uuid} cancellation was correct on executor')
            context['test_preparations'][test_plan_uuid]['updated_at'] = datetime.utcnow().replace(microsecond=0)
            context['test_preparations'][test_plan_uuid]['test_results'].append(payload)
            if test_uuid in context['events'][test_plan_uuid]:
                # app.logger.warning(f'Resuming test {test_uuid} cancelation process')
                _LOG.warning(f'Resuming test {test_uuid} cancelation process')
                context['events'][test_plan_uuid][test_uuid].set()
            else:
                # app.logger.warning(f'Test {test_uuid} appears to be canceled or non-existent')
                _LOG.warning(f'Test {test_uuid} appears to be canceled or non-existent')
        else:
            # app.logger.debug(f'Executor reported some error while cancelling test #{test_uuid}')
            _LOG.debug(f'Executor reported some error while cancelling test #{test_uuid}')
            context['test_preparations'][test_plan_uuid]['updated_at'] = datetime.utcnow().replace(microsecond=0)
            if test_uuid not in [result_entry['test_uuid'] for result_entry in context['test_preparations'][test_plan_uuid]['test_results']]:
                context['test_preparations'][test_plan_uuid]['test_results'].append(payload)
            else:
                for idx, item in enumerate(context['test_preparations'][test_plan_uuid]['test_results']):
                    if test_uuid == item['test_uuid']:
                        context['test_preparations'][test_plan_uuid]['test_results'][idx] = payload
                        break

            if test_uuid in context['events'][test_plan_uuid]:
                context['events'][test_plan_uuid][test_uuid].set()
            else:
                # app.logger.warning(f'Test {test_uuid} appears to be canceled or non-existent, or test failed')
                _LOG.warning(f'Test {test_uuid} appears to be canceled or non-existent, or test failed')
            process_thread = Thread(target=clean_environment, args=(test_plan_uuid, test_uuid, request.get_json(),))
            process_thread.start()
            context['threads'].append(process_thread)
    except Exception as e:
        tb = "".join(traceback.format_exc().split("\n"))
        # app.logger.error(f'Error in test_cancelled callback: {tb}')
        _LOG.error(f'Error in test_cancelled callback: {tb}')
        return make_response(json.dumps({'error': tb}), INTERNAL_ERROR, {'Content-Type': 'application/json'})
    return make_response('{"error": null}', OK, {'Content-Type': 'application/json'})


#  Future
# @app.route('/'.join(
#     ['', API_ROOT, API_VERSION, 'test-management', 'probes', 'prune']),
#     methods=['POST'])
# def clean_probe_inventory():
#     # Require login:password
#     return make_response('', OK)


#  Utils

@app.route('/'.join(['', API_ROOT, API_VERSION, 'context']), methods=['GET'])
def get_context():
    f_context = {k: context[k] for k in context.keys() if k != 'plugins' and k != 'threads' and k != 'events'}
    return make_response(
        json.dumps(f_context),
        OK,
        {'Content-Type': 'application/json'}
    )


@app.route('/'.join(['', API_ROOT, API_VERSION, 'config', 'mock']), methods=['POST'])
def configure_mock():
    payload = request.get_json()
    if 'mock_platform_adapter' in payload.keys() and payload['mock_platform_adapter']:
        pass # do mock PA
    if 'mock_executor' in payload.keys() and payload['mock_executor']:
        pass  # do mock X
    if 'mock_planner' in payload.keys() and payload['mock_planner']:
        pass  # do mock P


@app.route('/'.join(['', API_ROOT, API_VERSION, 'debugger']),methods=['GET', 'POST'])
def dummy_endpoint():
    try:
        if request.method == 'GET':
            # app.logger.debug(f'args: {request.args}')
            # app.logger.debug(f'path: {request.path}')
            # app.logger.debug(f'full_path: {request.full_path}')
            # app.logger.debug(f'url: {request.url}')
            _LOG.debug(f'args: {request.args}')
            _LOG.debug(f'path: {request.path}')
            _LOG.debug(f'full_path: {request.full_path}')
            _LOG.debug(f'url: {request.url}')
            return make_response('{"error": null}, {"message": "hello"}', OK, {'Content-Type': 'application/json'})
        elif request.method == 'POST':
            # app.logger.debug(f'headers: {request.headers}')
            # app.logger.debug(f'data:{request.get_data()}')
            _LOG.debug(f'headers: {request.headers}')
            _LOG.debug(f'data:{request.get_data()}')
            if request.headers['Content-type'] == 'application/json':
                # app.logger.debug(f'Content-type is json encoded! Content: {request.get_json()}')
                _LOG.debug(f'Content-type is json encoded! Content: {request.get_json()}')
            else:
                try:
                    # app.logger.debug(f'Content-type is NOT json encoded but it is json compatible, '
                    _LOG.debug(f'Content-type is NOT json encoded but it is json compatible, '
                                     f'Content: {json.loads(request.get_data().decode("UTF-8"))}')
                except:
                    # app.logger.debug(f'Data is not Json Serializable, Content: {request.get_data()}')
                    _LOG.debug(f'Data is not Json Serializable, Content: {request.get_data()}')

            return make_response(request.get_data(), OK, {'Content-type': request.headers['Content-type']})
        else:
            raise Exception('NOOOOOOOOOOOOOOOOOOOOOOOO')
    except Exception as e:
        return make_response(json.dumps({'error': ''.join(traceback.format_exc().split("\n"))}), INTERNAL_ERROR, {'Content-type': 'application/json'})


@app.errorhandler(NOT_FOUND)
def not_found(error):
    return make_response(json.dumps({'code': '404 Not Found', 'message': error.description}),
                         NOT_FOUND, {'Content-Type': 'application/json'})


@app.after_request
def after_request(response):
    # app.logger.info(f'{request.remote_addr} {request.scheme} {request.method}'
    _LOG.info(f'{request.remote_addr} {request.scheme} {request.method}'
              f' {request.full_path} {response.status} {response.content_length}')
    # response.headers.add('X-REQUEST-ID', current_request_id())
    return response


def main():
    context['alive_since'] = datetime.utcnow().replace(microsecond=0)
    context['test_preparations'] = {}
    context['test_results'] = []
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
    app.run(debug=False, host='0.0.0.0', port=context['host'].split(':')[1], threaded=True)


if __name__ == "__main__":
    main()
