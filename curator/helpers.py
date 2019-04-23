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

import time
import requests
import json
import logging
import threading
from curator.database import context
import curator.interfaces.vnv_components_interface as vnv_i
import curator.interfaces.common_databases_interface as db_i
import curator.interfaces.docker_interface as dock_i
from time import sleep
import traceback
from curator.logger import TangoLogger


# _LOG = TangoLogger.getLogger('flask.app', log_level=logging.DEBUG, log_json=True)
_LOG = logging.getLogger('flask.app')


def process_test_plan(test_plan_uuid):
    _LOG.info(f'Processing {test_plan_uuid}')
    # test_plan contains NSD and TD
    td = context['test_preparations'][test_plan_uuid]['testd']
    nsd = context['test_preparations'][test_plan_uuid]['nsd']
    context['test_preparations'][test_plan_uuid]['augmented_descriptors'] = []
    context['test_preparations'][test_plan_uuid]['test_results'] = []
    context['events'][test_plan_uuid] = {}
    planner = context['plugins']['planner']
    dockeri = context['plugins']['docker']
    # planner = vnv_i.PlannerInterface()
    # planner.add_new_test_plan(test_plan_uuid)
    platforms = td['service_platforms']  # should be a list
    platform_adapter = context['plugins']['platform_adapter']
    executor = context['plugins']['executor']
    vnv_cat = context['plugins']['catalogue']
    context['test_preparations'][test_plan_uuid]['probes'] = []
    _LOG.debug(f'testd: {td}')
    setup_phase = [phase for phase in td['phases'] if phase['id'] == 'setup'].pop()
    configuration_action = [step for step in setup_phase['steps'] if step['action'] == 'configure'].pop()
    _LOG.debug(f'configuration_phase: {configuration_action}')
    for probe in configuration_action['probes']:
        _LOG.debug(f'Getting {probe["name"]}')
        try:
            image = dockeri.pull(probe['image'])
            image_id = image.short_id
        except Exception as e:
            _LOG.exception(e)
            image_id = f'aa-bb-cc-dd-{probe["name"]}'

        context['test_preparations'][test_plan_uuid]['probes'].append(
            {
                'id': str(image_id).split(':')[1],
                'name': probe['name'],
                'image': probe['image']
            }
        )
        # _LOG.debug(f'Got {probe["name"]}, {image}')
    if type(platforms) is list:

        # Network service deployment, for each test
        for platform_type in platforms:
            _LOG.info(f'Accesing {platform_type}')
            if platform_type == 'SONATA':
                service_platform = platform_adapter.available_platforms_by_type(platform_type.lower())[0]
                # (jdelacruz) Until (vendor, name, version) is assured to be the same for the package than for
                # the nsd, I am keeping this previous block
                # _LOG.debug('Search package for nsd {vendor}:{name}:{version}'.format(**nsd))
                # package_info = vnv_cat.get_package_id_from_nsd_tuple(
                #     nsd['vendor'], nsd['name'], nsd['version'])
                # _LOG.debug(f'Matching package found {package_info["uuid"]}, transfer to {service_platform["name"]}')
                # _LOG.debug(f'Matching package found {package_info["uuid"]}, '
                #            f'instantiating in {service_platform["name"]}')
                _LOG.debug(f'Instantiating nsd {nsd["vendor"]}:{nsd["name"]}:{nsd["version"]}, '
                           f'in {service_platform["name"]}')
                instance_name = f"{td['name']}-{nsd['name']}-{service_platform['name']}"
                context['events'][test_plan_uuid][instance_name] = threading.Event()
                inst_result = platform_adapter.automated_instantiation_sonata(
                    service_platform['name'],
                    nsd['name'], nsd['vendor'], nsd['version'],
                    instance_name=instance_name,
                    test_plan_uuid=test_plan_uuid
                )
                if inst_result['error']:
                    # Error before instantiation
                    _LOG.error(f"ERROR Response from PA: {inst_result['error']}")
                    continue


                # _LOG.debug(f'After event is set {time.time()}, '
                #            f'E({context["events"][test_plan_uuid][instance_name].is_set()})')
                # ~LEGACY~
                # sp_package_process_uuid = platform_adapter.transfer_package_sonata(
                #     package_info, service_platform['name'])
                # sp_network_service = platform_adapter.get_service_uuid_sonata(
                #     service_platform['name'],
                #     nsd['name'], nsd['vendor'], nsd['version'])
                # _LOG.debug(f'Remote NS is {sp_network_service}, sending instantiation order')
                # sp_response = platform_adapter.instantiate_service_sonata(
                #     service_platform['name'], sp_network_service, td['name'])
                # if sp_response['error']:
                #     _LOG.error(f'NS {sp_network_service} instantiaton failed: {sp_response["error"]}')
                #     raise ConnectionError(sp_response['error'])
                # else:
                #     _LOG.info(f'NS {sp_network_service} instantiaton process started at {sp_response["id"]}')
                # wait_for_instatiation(service_platform['name'], sp_response['id'])
                # if platform_adapter.is_service_instantiation_ready(
                #         service_platform['name'], sp_response['id']):
                #     _LOG.debug(f'NS {sp_network_service} instantiaton process successful')
                # :5001/adapters/qual_sp/instantiations/< id >/monitoring
                # headers = {"Content-type": "application/json"}
                # nsr = requests.get(f"qual-sp-bcn:4012/nsrs/{sp_response['instance_uuid']}", headers=headers)
                # for vnfr_ref in nsr['network_functions']:
                #   vnfr_rec.append(requests.get(f"qual-sp-bcn:4012/nsrs/{sp_response['instance_uuid']}).json())
                _LOG.debug(f'Waiting for event {test_plan_uuid}.{instance_name}, '
                           f'E({context["events"][test_plan_uuid][instance_name].is_set()})')
                context["events"][test_plan_uuid][instance_name].wait()
                _LOG.debug(f"Received parameters from SP: "
                           f"{context['test_preparations'][test_plan_uuid]['augmented_descriptors']}")
                instantiation_params = [
                    (p_index, augd) for p_index, augd in
                    enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
                    if augd['platform']['platform_type'] == platform_type.lower() and not augd['error']
                ]
                if len(instantiation_params) < 1:
                    error_params = instantiation_params = [
                        (p_index, augd) for p_index, augd in
                        enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
                        if augd['error'] and augd['nsi_name'] == instance_name
                    ]
                    if error_params:
                        _LOG.error(f'Received error from PA: {error_params}')
                        # Prepare callback to planner
                        continue

                test_cat = vnv_cat.get_test_descriptor_tuple(td['vendor'], td['name'], td['version'])
                nsd_cat = vnv_cat.get_network_descriptor_tuple(nsd['vendor'], nsd['name'], nsd['version'])
                if len(test_cat) == 0:
                    _LOG.warning('Test was not found in V&V catalogue, using a mock uuid')
                    test_cat = [{'uuid': 'deb05341-1337-1337-1337-1c3ecd41e51d'}]
                if len(nsd_cat) == 0:
                    _LOG.warning('Nsd was not found in V&V catalogue, using a mock uuid')
                    nsd_cat = [{'uuid': 'deb05341-1337-1337-1337-1c3ecd44e75d'}]
                try:
                    test_descriptor_instance = generate_test_descriptor_instance(
                        td.copy(),
                        instantiation_params[0][1]['functions'],
                        test_uuid=test_cat[0]['uuid'],
                        service_uuid=nsd_cat[0]['uuid'],
                        package_uuid=inst_result['package_id'],
                        instance_uuid=instantiation_params[0][1]['nsi_uuid']
                    )
                    _LOG.debug(f'Generated tdi: {json.dumps(test_descriptor_instance)}, sending to executor')
                    ex_response = executor.execution_request(test_descriptor_instance, test_plan_uuid)
                    (context['test_preparations'][test_plan_uuid]
                        ['augmented_descriptors'][instantiation_params[0][0]]
                        ['platform']['name']) = service_platform['name']
                    (context['test_preparations'][test_plan_uuid]
                        ['augmented_descriptors'][instantiation_params[0][0]]
                        ['tdi']) = test_descriptor_instance
                    (context['test_preparations'][test_plan_uuid]
                        ['augmented_descriptors'][instantiation_params[0][0]]
                        ['test_uuid']) = ex_response['test_uuid']
                    (context['test_preparations'][test_plan_uuid]
                        ['augmented_descriptors'][instantiation_params[0][0]]
                        ['test_status']) = ex_response['status'] if 'status' in ex_response.keys() else 'UNKNOWN'
                    del context['events'][test_plan_uuid][instance_name]
                    _LOG.debug(f'Response from executor: {ex_response}')

                except Exception as e:
                    tb = "".join(traceback.format_exc().split("\n"))
                    _LOG.error(f'Error during test execution: {tb}')
                    (context['test_preparations'][test_plan_uuid]['augmented_descriptors'][instantiation_params[0][0]]
                        ['test_status']) = 'ERROR'
                # # Wait for executor callback (?)
                # context['events'][instance_name].set()
                # context['events'][instance_name].wait()
                # loop = True
                # while loop:
                #     if (context['test_preparations'][test_plan_uuid]
                #             ['augmented_descriptors'][instantiation_params[0]]
                #             ['test_status']) == 'RUNNING':
                #         pass  # do running thing
                #     elif (context['test_preparations'][test_plan_uuid]
                #             ['augmented_descriptors'][instantiation_params[0]]
                #             ['test_status']) == 'ERROR':
                #         pass  # do running thing
                #     elif (context['test_preparations'][test_plan_uuid]
                #             ['augmented_descriptors'][instantiation_params[0]]
                #             ['test_status']) == 'COMPLETED':
                #         pass  # do running thing
                #     elif (context['test_preparations'][test_plan_uuid]
                #             ['augmented_descriptors'][instantiation_params[0]]
                #             ['test_status']) == 'ERROR':
                #         pass  # do running thing

            elif platform_type == 'OSM':
                # TODO
                sp = platform_adapter.available_platforms_by_type(platform_type.lower())[0]
                # Use uuids, search for nsd and vnfd (or pass nsd uuid to PA and it will go forward)
                pass
            elif platform_type == 'ONAP':
                # TODO
                pass
            else:
                _LOG.warning(f'Platform {platform_type} is not compatible')

    else:
        _LOG.error(f'Wrong platform value, should be a list and is a {type(platforms)}')
        try:
            callback_path = [
                d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                if d['status'] == 'COMPLETED'
            ][0]
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR')
        except AttributeError as e:
            # _LOG.exception(e)
            _LOG.error(f'Callbacks: {e} but going fallback to /test-plans/on-change/completed')
            planner.send_callback('/test-plans/on-change/completed', test_plan_uuid, result_list=[], status='ERROR')

    if not context['test_preparations'][test_plan_uuid]['augmented_descriptors']:
        # No correct test executions, sendind callback
        _LOG.warning(f'Curator was not able to setup any of the test environments for {test_plan_uuid}, '
                     f'sending callback to planner')
        try:
            callback_path = [
                d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                if d['status'] == 'COMPLETED'
            ][0]
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR')
        except AttributeError as e:
            # _LOG.exception(e)
            _LOG.error(f'Callbacks: {e} but going fallback to /test-plans/on-change/completed')
            planner.send_callback('/test-plans/on-change/completed', test_plan_uuid, result_list=[], status='ERROR')
    # LOG.debug('completed ' + test_plan)


def clean_environment(test_plan_uuid, test_id=None, content=None, error=None):
    _LOG.info(f'Test {test_id} from test-plan {test_plan_uuid} finished')
    _LOG.debug(f'Callback content: {content}')
    platform_adapter = context['plugins']['platform_adapter']
    dockeri = context['plugins']['docker']
    planner = context['plugins']['planner']
    try:
        callback_path = [
            d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
            if d['status'] == 'COMPLETED'
        ][0]
    except AttributeError as e:
        # _LOG.exception(e)
        _LOG.error(f'Callbacks: {e} but going forward')
        callback_path = ''
    if not error and content:
        context['test_preparations'][test_plan_uuid]['test_results'].append(content)
        context['test_results'].append(content)  # just for debugging
        test_finished = [
            (p_index, augd) for p_index, augd in
            enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
            if augd['test_uuid'] == test_id
        ][0]
        (context['test_preparations'][test_plan_uuid]['augmented_descriptors']
            [test_finished[0]]['test_status']) = content['status'] if 'status' in content.keys() else 'FINISHED'


        #  Shutdown instance
        # _LOG.debug(f'Termination surpressed for {test_finished[1]["nsi_uuid"]} on {test_finished[1]["platform"]}')
        _LOG.debug(f'Terminating service instance {test_finished[1]["nsi_uuid"]} on {test_finished[1]["platform"]}')
        pa_termination_response = platform_adapter.shutdown_package(
            test_finished[1]['platform']['name'],
            test_finished[1]['nsi_uuid'])
        _LOG.debug(f'Termination response from PA: {pa_termination_response}')
        # pa_package_removal_response = platform_adapter.delete_package(
        #     test_finished[1]['platform_type'],
        #     test_finished[1]['tdi']['package_uuid']
        #     'p_name'
        # )
        # TODO: remove package from SP
    elif error:
        pass
    if all([d['test_status'] != 'STARTING' and d['test_status'] != 'RUNNING'
            for d in context['test_preparations'][test_plan_uuid]['augmented_descriptors']]):
        #  Remove probe images if there are no more instances running on this test plan
        _LOG.debug(f'Test {test_id} was the last for test-plan {test_plan_uuid}, '
                   f'cleaning up and sending results to planner')
        for probe in context['test_preparations'][test_plan_uuid]['probes']:
            try:
                _LOG.debug(f'Removing {probe["name"]}')
                dockeri.rm_image(probe['image'])
            except Exception as e:
                _LOG.exception(f'Failed removal of {probe["name"]}, reason: {e}')

        #  Answer to planner
        try:
            res_list = [
                {
                    'test_uuid': d['test_uuid'],
                    'test_results_uuid': d['results_uuid'],
                    'test_status': d['status']
                }
                for d in context['test_preparations'][test_plan_uuid]['test_results'] if d is not None
            ]
            _LOG.debug(f'results for test_plan #{test_plan_uuid}: {res_list}')
            planner_resp = planner.send_callback(callback_path, test_plan_uuid, res_list, status='COMPLETED')
            _LOG.debug(f'Response from planner: {planner_resp}')
            # if planner_resp ok, clean test_preparations entry
            del context['test_preparations'][test_plan_uuid]
        except Exception as e:
            tb = "".join(traceback.format_exc().split("\n"))
            _LOG.error(f'Error during test_results recovery: {tb}')
            planner_resp = planner.send_callback(callback_path, test_plan_uuid, [], status='ERROR')
            _LOG.debug(f'Response from planner (Errback): {planner_resp}')


def test_status_update(test_plan_uuid, test_id, content):
    pass


def execute_test_plan():
    # TODO: execute tests inside test_plan
    # For the moment we have only 1 test per test_plan
    pass


def cancel_test_plan(test_plan_uuid, content):
    """
    Cancel all running tests on that test_bundle
    and return response to planner
    :param test_plan_uuid:
    :param content:
    :return:
    """
    _LOG.info(f'Canceling test-plan {test_plan_uuid} by planner request')
    planner = context['plugin']['planner']
    executor = context['plugin']['executor']
    dockeri = context['plugins']['docker']
    callback_path = context['test_preparations'][test_plan_uuid]['test_plan_callbacks'][1]['url']  #FIXME
    for test in [run_test for run_test in context['test_preparations'][test_plan_uuid]['augmented_descriptors']
                 if run_test['test_status'] == 'RUNNING' or run_test['test_status'] == 'STARTING']:
        context['events'][test_plan_uuid][test['test_uuid']] = threading.Event()
        executor.execution_cancel(test_plan_uuid, test['test_uuid'])
        context['events'][test_plan_uuid][test['test_uuid']].wait()
        del context['events'][test_plan_uuid][test['test_uuid']]

    _LOG.debug(f'Finished cancelation for test-plan {test_plan_uuid}, '
               f'cleaning up and sending results to planner')
    for probe in context['test_preparations'][test_plan_uuid]['probes']:
        dockeri.rm_image(probe['image'])
        #  Answer to planner
    planner_resp = planner.send_callback(callback_path, test_plan_uuid,
                                         context['test_preparations'][test_plan_uuid]['test_results'],
                                         status='CANCELLED'
                                         )
    # if planner_resp ok, clean test_preparations entry

    del context['test_preparations'][test_plan_uuid]


def generate_test_descriptor_instance(test_descriptor, instantiation_parameters,
                                      test_uuid=None, service_uuid=None,
                                      package_uuid=None, instance_uuid=None):
    """
    This method searchs for parameters to be written with instantiation parameters and then writes them into the
    augmented descriptor, and returns it
    :param test_descriptor:
    :param instantiation_parameters:
    :param test_uuid:
    :param service_uuid:
    :param package_uuid:
    :param instance_uuid:
    :return:
    """
    _LOG.debug(f'Parsing instantiation parameters, {vars()}')
    setup_phase = [(i, phase) for i, phase in enumerate(test_descriptor['phases']) if phase['id'] == 'setup'].pop()
    configuration_action = [(i, step) for i, step in enumerate(setup_phase[1]['steps']) if step['action'] == 'configure'].pop()
    # configuration_action = [
    #     [
    #         (i, step) for i, step in enumerate(setup_phase['steps'])
    #         if step['action'] == 'configure'
    #     ]
    #     for setup_phase in test_descriptor['phases'] if setup_phase['id'] == 'setup'
    # ][0][0]
    for probe in configuration_action[1]['probes']:
        if 'parameters' in probe.keys():
            for i, probe_param in enumerate(probe['parameters']):
                if probe_param['value'].startswith('$(') and probe_param['value'].endswith(')'):
                    path = probe_param['value'].strip('$()').split('/')
                    for parameter in instantiation_parameters:
                        if parameter['name'] == path[0]:
                            value = route_from_text(parameter, path[1:])
                            probe_param['value'] = value
    # TODO: warn or error when there are expected parameters that are missing
    test_descriptor['test_descriptor_uuid'] = test_uuid
    test_descriptor['package_descriptor_uuid'] = package_uuid
    test_descriptor['network_service_descriptor_uuid'] = service_uuid
    test_descriptor['service_instance_uuid'] = instance_uuid
    _LOG.debug(test_descriptor)
    return test_descriptor


def wait_for_instatiation(platform_adapter, service_platform, service_uuid, period=5, timeout=None):
    """
    Method for waiting for SP to instantiate the service, in case PA has not callback
    :param service_platform:
    :param service_uuid:
    :return:
    """
    _LOG.debug(f'Wait until service {service_uuid} is READY')
    status = None
    # TODO Establish timeout or thread will hang here
    while status != 'READY':
        r = platform_adapter.get_service_instantiation(service_platform, service_uuid)
        status = r['status']
        if status != 'READY':
            sleep(period)


def route_from_text(obj, route):
    """
    Recursive function to look for the requested object
    :param obj:
    :param route:
    :return:
    """
    _LOG.debug(f'Looking for {route} in {obj}')
    if len(route) > 1 and ':' in route[0]:
        _LOG.debug('Is a dictionary nested inside a list')
        res = [d for d in obj if d[route[0].split(':')[0]] == route[0].split(':')[1]][0]
        tail = route_from_text(res, route[1:])
    elif len(route) > 1 and ':' not in route[0]:
        _LOG.debug('Is a dictionary nested inside a dictionary')
        res = obj[route[0]]
        tail = route_from_text(res, route[1:])
    elif len(route) == 1:
        _LOG.debug('Is an object')
        tail = obj[route[0]]
    else:
        raise ValueError(obj, route)
    return tail

