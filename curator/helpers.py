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
import random
import os
from curator.database import context
import curator.interfaces.vnv_components_interface as vnv_i
import curator.interfaces.common_databases_interface as db_i
import curator.interfaces.docker_interface as dock_i
from time import sleep
import traceback
from curator.logger import TangoLogger


_LOG = TangoLogger.getLogger('curator:backend', log_level=logging.DEBUG, log_json=True)
# _LOG = logging.getLogger('flask.app')


def process_test_plan(test_plan_uuid):
    _LOG.info(f'Processing {test_plan_uuid}')
    # test_plan contains NSD and TD
    context['test_preparations'][test_plan_uuid]['augmented_descriptors'] = []
    context['test_preparations'][test_plan_uuid]['test_results'] = []
    context['events'][test_plan_uuid] = {}
    planner = context['plugins']['planner']
    execution_host = context['test_preparations'][test_plan_uuid].get('execution_host')
    err_msg = None
    try:
        if not execution_host:
            dockeri = context['plugins']['docker']
        else:
            dockeri = dock_i.DockerInterface(execution_host=execution_host)
            context['test_preparations'][test_plan_uuid]['docker_interface'] = dockeri
    except Exception as e:
        err_msg = f'Exception when connecting to execution host: {e}'
        _LOG.error(err_msg)
        callback_path = '/api/v1/test-plans/on-change/completed'
        planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
        return

    # planner = vnv_i.PlannerInterface()
    # planner.add_new_test_plan(test_plan_uuid)
    platform_adapter = context['plugins']['platform_adapter']
    executor = context['plugins']['executor']
    vnv_cat = context['plugins']['catalogue']
    load_balancer_algorithm = os.getenv('LB_ALGO','random')
    err_msg = None
    try:
        callback_path = [
            d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
            if d['status'] == 'COMPLETED'
        ][0]
    except AttributeError as e:
        # _LOG.exception(e)
        err_msg = f'Error reading callbacks: {e} but using /test-plans/on-change/completed'
        _LOG.error(err_msg)
        callback_path = '/api/v1/test-plans/on-change/completed'

    if 'testd' in context['test_preparations'][test_plan_uuid]:
        _LOG.warning('Overriding testd_uuid by testd')
        td = context['test_preparations'][test_plan_uuid]['testd']
        del context['test_preparations'][test_plan_uuid]['testd_uuid']
    else:
        try:
            raw_td = vnv_cat.get_test_descriptor(context['test_preparations'][test_plan_uuid]['testd_uuid'])
            td = raw_td['testd']
        except Exception as e:
            err_msg = f'Error when accesing TD: {e}'
            _LOG.error(err_msg)
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
            return

    # OPTIONAL: get sp_name if it is in the payload, None elsecase
    sp_name = context['test_preparations'][test_plan_uuid].get('sp_name')

    # NOTE: support for several nsds (same kind) -> NO
    # for nsd in context['test_preparations'][test_plan_uuid]['nsd_batch']
    # FIXME: nsd doesn't have platform key
    if 'nsd' in context['test_preparations'][test_plan_uuid] and \
            context['test_preparations'][test_plan_uuid]['nsd']['platform'] == '5gtango':
        _LOG.warning('Overriding nsd_uuid by nsd, nsd platform is 5gtango')
        nsd = context['test_preparations'][test_plan_uuid]['nsd']
        del context['test_preparations'][test_plan_uuid]['nsd_uuid']
    elif 'nsd' in context['test_preparations'][test_plan_uuid] and \
            context['test_preparations'][test_plan_uuid]['nsd']['platform'] == 'osm':
        _LOG.warning('Overriding nsd_uuid by nsd, nsd platform is osm')
        nsd = context['test_preparations'][test_plan_uuid]["nsd"]["nsd:nsd-catalog"]["nsd"][0]
        del context['test_preparations'][test_plan_uuid]['nsd_uuid']
    else:
        try:
            raw_nsd = vnv_cat.get_network_descriptor(context['test_preparations'][test_plan_uuid]['nsd_uuid'])
            if raw_nsd['platform'].lower() == '5gtango':
                nsd_target = raw_nsd['platform'].lower()
                nsd = raw_nsd['nsd']
            elif raw_nsd['platform'].lower() == 'sonata':
                nsd_target = raw_nsd['platform'].lower()
                nsd = raw_nsd['nsd']
            elif raw_nsd['platform'].lower() == 'osm':
                nsd_target = raw_nsd['platform'].lower()
                if type(raw_nsd["nsd"]["nsd:nsd-catalog"]["nsd"]) is list and len(raw_nsd["nsd"]["nsd:nsd-catalog"]["nsd"]) == 1:
                    nsd = raw_nsd["nsd"]["nsd:nsd-catalog"]["nsd"][0]
                elif type(raw_nsd["nsd"]["nsd:nsd-catalog"]["nsd"]) is dict:
                    nsd = raw_nsd["nsd"]["nsd:nsd-catalog"]["nsd"]
                elif type(raw_nsd["nsd"]["nsd:nsd-catalog"]["nsd"]) is list and len(raw_nsd["nsd"]["nsd:nsd-catalog"]["nsd"]) > 1:
                    raise NotImplementedError('VnV is not compatible with multi-service network services')
                else:
                    raise ValueError('VnV is not compatible with this network service descriptor')
        except Exception as e:
            err_msg = f'Error when accesing NSD: {e}'
            _LOG.error(err_msg)
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
            return
    platforms = td.get('service_platforms')  # should be a list not null
    if not platforms:
        err_msg = f'"service_platforms" field in test descriptor is required, found {platforms}'
        _LOG.error(err_msg)
        planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
        return
    context['test_preparations'][test_plan_uuid]['probes'] = []
    _LOG.debug(f'testd: {td}, nsd: {nsd}, nsd_target: {nsd_target}')
    # TODO: get nsd and testd if only uuid is included (normal function) and avoid
    # it if there's testd and/or nsd included in the payload
    setup_phase = [phase for phase in td['phases'] if phase['id'] == 'setup'].pop()
    configuration_action = [step for step in setup_phase['steps'] if step['action'] == 'configure'].pop()
    _LOG.debug(f'configuration_phase: {configuration_action}')
    for probe in configuration_action['probes']:
        _LOG.debug(f'Getting {probe["name"]}')
        try:
            if len(probe['image'].split(':')) == 1:
                _LOG.warning(f'{probe["image"]} tag is not specified, using latest instead')
                image = dockeri.pull(':'.join([probe['image'], 'latest']))
            elif len(probe['image'].split(':')) == 2:
                image = dockeri.pull(probe['image'])
            else:
                raise Exception('Probe image name was wrongly formatted?')

            if image:
                context['test_preparations'][test_plan_uuid]['probes'].append(
                    {
                        'id': str(image.short_id).split(':')[1],
                        'name': probe['name'],
                        'image': probe['image']
                    }
                )
                _LOG.debug(f'Got {probe["name"]}, {image}')
            else:
                err_msg = f'Exception getting probe {probe["name"]}: Image not found'
                _LOG.error(err_msg)
        except Exception as e:
            err_msg = f'Exception getting probe {probe["name"]}: {e}'
            _LOG.error(err_msg)

    if not err_msg and type(platforms) is list:
        if 'SONATA' in platforms and (nsd_target == '5gtango' or nsd_target == 'sonata'):
            _LOG.info(f"Accesing {nsd_target}")
            platform_type = 'SONATA'
            policy_id = context['test_preparations'][test_plan_uuid].get('policy_id')
            sp_list = platform_adapter.available_platforms_by_type(platform_type.lower())
            if not sp_list:
                err_msg = f'No available platforms of type {platform_type}'
                _LOG.error(err_msg)
                try:
                    callback_path = [
                        d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                        if d['status'] == 'COMPLETED'
                    ][0]
                    planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR',
                                          exception=err_msg)
                    return
                except AttributeError as e:
                    # _LOG.exception(e)
                    err_msg = f'Callbacks: {e} but going fallback to /test-plans/on-change/completed'
                    _LOG.error(err_msg)
                    planner.send_callback('/test-plans/on-change/completed', test_plan_uuid, result_list=[],
                                          status='ERROR', exception=err_msg)
                    return
            elif sp_name:
                _LOG.debug(f"Overriding with service platform {sp_name}")
                service_platform = [sp for sp in sp_list if sp['name'] == sp_name].pop()
            elif load_balancer_algorithm == 'random':
                _LOG.debug(f"Using {load_balancer_algorithm} load balancer")
                service_platform = random.choice(sp_list)
                _LOG.debug(f"Platform {service_platform} selected")
            elif load_balancer_algorithm == 'round_robin':
                _LOG.debug(f"Using {load_balancer_algorithm} load balancer")
                if platform_adapter.sonata_sp_usage_count:
                    least_used_son_sp = sorted(
                        platform_adapter.sonata_sp_usage_count,
                        key=platform_adapter.sonata_sp_usage_count.get)[0]
                    platform_match_list = [sp for sp in sp_list if sp['name'] == least_used_son_sp]
                    if platform_match_list:
                        service_platform = platform_match_list[0]
                        platform_adapter.sonata_sp_usage_count[least_used_son_sp] += 1
                    else:
                        service_platform = random.choice(sp_list)
                        platform_adapter.sonata_sp_usage_count[service_platform['name']] = 1
                else:
                    service_platform = random.choice(sp_list)
                    platform_adapter.sonata_sp_usage_count[service_platform['name']] = 1
                _LOG.debug(f"Platform {service_platform} selected")
            else:
                _LOG.warning(f"No load balancer selected")
                service_platform = platform_adapter.available_platforms_by_type(platform_type.lower())[0]
                _LOG.debug(f"Platform {service_platform} selected")
            _LOG.debug(f'Instantiating nsd {nsd["vendor"]}:{nsd["name"]}:{nsd["version"]}, '
                       f'in {service_platform["name"]}')
            instance_name = f"{td['name']}-{nsd['name']}-{service_platform['name']}"
            instantiation_init = time.time()
            inst_result = platform_adapter.automated_instantiation_sonata(
                service_platform['name'],
                nsd['name'], nsd['vendor'], nsd['version'],
                instance_name=instance_name,
                test_plan_uuid=test_plan_uuid,
                policy_id=policy_id
            )
            if 'error' in inst_result and inst_result['error']:
                # Error before instantiation
                _LOG.error(f"SONATA ERROR Response from PA: {inst_result['error']}")
                err_msg = inst_result['error']

            else:
                context['events'][test_plan_uuid][instance_name] = threading.Event()
                _LOG.debug(f'Waiting for event {test_plan_uuid}.{instance_name}, '
                           f'E({context["events"][test_plan_uuid][instance_name].is_set()})')
                context["events"][test_plan_uuid][instance_name].wait()
                instantiation_end = time.time()
                del context['events'][test_plan_uuid][instance_name]
                _LOG.debug(f"Received parameters from SP: "
                           f"{context['test_preparations'][test_plan_uuid]['augmented_descriptors']}")
                instantiation_params = [
                    (p_index, augd) for p_index, augd in
                    enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
                    if augd['platform']['platform_type'] == platform_type.lower() and not augd['error']
                ]
                if len(instantiation_params) < 1:
                    error_params = [
                        (p_index, augd) for p_index, augd in
                        enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
                        if augd['error'] and augd['nsi_name'] == instance_name
                    ].pop()
                    if error_params:
                        _LOG.error(f'Received error from PA: {error_params[1]}')
                        (context['test_preparations'][test_plan_uuid]
                            ['augmented_descriptors'][error_params[0]]['test_status']) = 'ERROR'
                        (context['test_preparations'][test_plan_uuid]['augmented_descriptors']
                            [error_params[0]]['error']) = f'PA: {error_params[1].get("error")}'
                        err_msg = context['test_preparations'][test_plan_uuid]['augmented_descriptors'][error_params[0]]['error']
                        _LOG.error(f'Error processed for {test_plan_uuid}: {err_msg}')
                        # Prepare callback to planner
                else:
                    (context['test_preparations'][test_plan_uuid]['augmented_descriptors']
                        [instantiation_params[0][0]]['package_uploaded']) = inst_result['package_uploaded'] \
                        if 'package_uploaded' in inst_result else False
                    if 'testd_uuid' not in context['test_preparations'][test_plan_uuid]:
                        test_cat = vnv_cat.get_test_descriptor_tuple(td['vendor'], td['name'], td['version'])
                        if len(test_cat) == 0:
                            _LOG.warning('Test was not found in V&V catalogue, using a mock uuid')
                            context['test_preparations'][test_plan_uuid]['testd_uuid'] = 'deb05341-1337-1337-1337-1c3ecd41e51d'
                        else:
                            context['test_preparations'][test_plan_uuid]['testd_uuid'] = test_cat[0]['uuid']
                    if 'nsd_uuid' not in context['test_preparations'][test_plan_uuid]:
                        nsd_cat = vnv_cat.get_network_descriptor_tuple(nsd['vendor'], nsd['name'], nsd['version'])
                        if len(nsd_cat) == 0:
                            _LOG.warning('Nsd was not found in V&V catalogue, using a mock uuid')
                            context['test_preparations'][test_plan_uuid]['nsd_uuid'] = 'deb05341-1337-1337-1337-1c3ecd44e75d'
                        else:
                            context['test_preparations'][test_plan_uuid]['nsd_uuid'] = nsd_cat[0]['uuid']
                    try:
                        test_descriptor_instance = generate_test_descriptor_instance(
                            td.copy(),
                            instantiation_params[0][1]['functions'],
                            test_uuid=context['test_preparations'][test_plan_uuid]['testd_uuid'],
                            service_uuid=context['test_preparations'][test_plan_uuid]['nsd_uuid'],
                            package_uuid=inst_result['package_id'],
                            instance_uuid=instantiation_params[0][1]['nsi_uuid']
                        )
                        _LOG.debug(f'Generated tdi: {json.dumps(test_descriptor_instance)}, sending to executor')
                        ex_response = executor.execution_request(
                            test_descriptor_instance, test_plan_uuid,
                            service_instantiation_time=instantiation_end-instantiation_init,
                            docker_host=context['test_preparations'][test_plan_uuid].get('execution_host')
                        )
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
                        # del context['events'][test_plan_uuid][instance_name]
                        _LOG.debug(f'Response from executor: {ex_response}')

                    except Exception as e:
                        tb = "".join(traceback.format_exc().split("\n"))
                        _LOG.error(f'Error during test execution: {tb}')
                        (context['test_preparations'][test_plan_uuid]['augmented_descriptors'][instantiation_params[0][0]]
                        ['test_status']) = 'ERROR'
                        (context['test_preparations'][test_plan_uuid]['augmented_descriptors'][instantiation_params[0][0]]
                        ['error']) = tb

        elif 'OSM' in platforms and nsd_target == 'osm':
            _LOG.info(f"Accesing {nsd_target}")
            platform_type = 'OSM'
            sp_list = platform_adapter.available_platforms_by_type(platform_type.lower())
            if not sp_list:
                err_msg = f'No available platforms of type {platform_type}'
                _LOG.error(err_msg)
                try:
                    callback_path = [
                        d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                        if d['status'] == 'COMPLETED'
                    ][0]
                    planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR',
                                          exception=err_msg)
                    return
                except AttributeError as e:
                    # _LOG.exception(e)
                    err_msg = f'Callbacks: {e} but going fallback to /test-plans/on-change/completed'
                    _LOG.error(err_msg)
                    planner.send_callback('/test-plans/on-change/completed', test_plan_uuid, result_list=[],
                                          status='ERROR', exception=err_msg)
                    return
            elif sp_name:
                _LOG.debug(f"Overriding with service platform {sp_name}")
                service_platform = [sp for sp in sp_list if sp['name'] == sp_name].pop()
            elif load_balancer_algorithm == 'random':
                _LOG.debug(f"Using {load_balancer_algorithm} load balancer")
                service_platform = random.choice(sp_list)
                _LOG.debug(f"Platform {service_platform} selected")
            elif load_balancer_algorithm == 'round_robin':
                _LOG.debug(f"Using {load_balancer_algorithm} load balancer")
                if platform_adapter.osm_sp_usage_count:
                    least_used_son_sp = sorted(
                        platform_adapter.osm_sp_usage_count,
                        key=platform_adapter.osm_sp_usage_count.get)[0]
                    platform_match_list = [sp for sp in sp_list if sp['name'] == least_used_son_sp]
                    if platform_match_list:
                        service_platform = platform_match_list[0]
                        platform_adapter.osm_sp_usage_count[least_used_son_sp] += 1
                    else:
                        service_platform = random.choice(sp_list)
                        platform_adapter.osm_sp_usage_count[service_platform['name']] = 1
                else:
                    service_platform = random.choice(sp_list)
                    platform_adapter.osm_sp_usage_count[service_platform['name']] = 1
                _LOG.debug(f"Platform {service_platform} selected")
            else:
                _LOG.warning(f"No load balancer selected")
                service_platform = platform_adapter.available_platforms_by_type(platform_type.lower())[0]
                _LOG.debug(f"Platform {service_platform} selected")
            _LOG.debug(f'Instantiating nsd {nsd["vendor"]}:'
                       f'{nsd["name"]}:'
                       f'{nsd["version"]}, '
                       f'in {service_platform["name"]}')
            instance_name = f'{td["name"]}-{nsd["name"]}-{service_platform["name"]}'
            instantiation_init = time.time()
            inst_result = platform_adapter.automated_instantiation_osm(
                service_platform['name'],
                nsd['name'],
                nsd['vendor'],
                nsd['version'],
                instance_name=instance_name,
                test_plan_uuid=test_plan_uuid
            )
            if 'error' in inst_result and inst_result['error']:
                # Error before instantiation
                _LOG.error(f"OSM ERROR Response from PA: {inst_result['error']}")
                err_msg = inst_result['error']

            else:
                context['events'][test_plan_uuid][instance_name] = threading.Event()

                _LOG.debug(f'Waiting for event {test_plan_uuid}.{instance_name}, '
                           f'E({context["events"][test_plan_uuid][instance_name].is_set()})')
                context["events"][test_plan_uuid][instance_name].wait()
                instantiation_end = time.time()
                del context['events'][test_plan_uuid][instance_name]
                _LOG.debug(f"Received parameters from SP: "
                           f"{context['test_preparations'][test_plan_uuid]['augmented_descriptors']}")
                instantiation_params = [
                    (p_index, augd) for p_index, augd in
                    enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
                    if augd['platform']['platform_type'] == platform_type.lower() and not augd['error']
                ]
                if len(instantiation_params) < 1:
                    error_params = [
                        (p_index, augd) for p_index, augd in
                        enumerate(context['test_preparations'][test_plan_uuid]['augmented_descriptors'])
                        if augd['error'] and augd['nsi_name'] == instance_name
                    ].pop()
                    if error_params:
                        _LOG.error(f'Received error from PA: {error_params[1]}')
                        (context['test_preparations'][test_plan_uuid]
                            ['augmented_descriptors'][error_params[0]]['test_status']) = 'ERROR'
                        (context['test_preparations'][test_plan_uuid]['augmented_descriptors']
                            [error_params[0]]['error']) = f'PA: {error_params[1].get("error")}'
                        err_msg = context['test_preparations'][test_plan_uuid]['augmented_descriptors'][error_params[0]]['error']
                        # Prepare callback to planner
                else:
                    (context['test_preparations'][test_plan_uuid]['augmented_descriptors']
                        [instantiation_params[0][0]]['package_uploaded']) = inst_result['package_uploaded'] \
                            if 'package_uploaded' in inst_result else False
                    if 'testd_uuid' not in context['test_preparations'][test_plan_uuid]:
                        test_cat = vnv_cat.get_test_descriptor_tuple(td['vendor'], td['name'], td['version'])
                        if len(test_cat) == 0:
                            _LOG.warning('Test was not found in V&V catalogue, using a mock uuid')
                            context['test_preparations'][test_plan_uuid]['testd_uuid'] = 'deb05341-1337-1337-1337-1c3ecd41e51d'
                        else:
                            context['test_preparations'][test_plan_uuid]['testd_uuid'] = test_cat[0]['uuid']
                    if 'nsd_uuid' not in context['test_preparations'][test_plan_uuid]:
                        nsd_cat = vnv_cat.get_network_descriptor_tuple(nsd['vendor'], nsd['name'], nsd['version'])
                        if len(nsd_cat) == 0:
                            _LOG.warning('Nsd was not found in V&V catalogue, using a mock uuid')
                            context['test_preparations'][test_plan_uuid]['nsd_uuid'] = 'deb05341-1337-1337-1337-1c3ecd44e75d'
                        else:
                            context['test_preparations'][test_plan_uuid]['nsd_uuid'] = nsd_cat[0]['uuid']
                    try:
                        test_descriptor_instance = generate_test_descriptor_instance(
                            td.copy(),
                            instantiation_params[0][1]['functions'],
                            test_uuid=context['test_preparations'][test_plan_uuid]['testd_uuid'],
                            service_uuid=context['test_preparations'][test_plan_uuid]['nsd_uuid'],
                            package_uuid=inst_result['package_id'],
                            instance_uuid=instantiation_params[0][1]['nsi_uuid']
                        )
                        _LOG.debug(f'Generated tdi: {json.dumps(test_descriptor_instance)}, sending to executor')
                        ex_response = executor.execution_request(
                            test_descriptor_instance, test_plan_uuid,
                            service_instantiation_time=instantiation_end-instantiation_init,
                            docker_host=context['test_preparations'][test_plan_uuid].get('execution_host')
                        )
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
                        # del context['events'][test_plan_uuid][instance_name]
                        _LOG.debug(f'Response from executor: {ex_response}')

                    except Exception as e:
                        tb = "".join(traceback.format_exc().split("\n"))
                        _LOG.error(f'Error during test execution: {tb}')
                        (context['test_preparations'][test_plan_uuid]['augmented_descriptors'][instantiation_params[0][0]]
                            ['test_status']) = 'ERROR'
                        (context['test_preparations'][test_plan_uuid]['augmented_descriptors'][instantiation_params[0][0]]
                            ['error']) = tb

        elif 'ONAP' in platforms and nsd_target == 'onap':
            _LOG.info(f"Accesing {nsd_target}")
            platform_type = 'ONAP'
            _LOG.error(f'Platform {platform_type} not yet implemented')
        else:
            _LOG.warning(f"Platform {nsd_target} is not compatible")

    elif not err_msg:
        err_msg = f'Wrong platform value, should be a list and is a {type(platforms)}'
        _LOG.error(err_msg)
        try:
            callback_path = [
                d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                if d['status'] == 'COMPLETED'
            ][0]
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
            return
        except AttributeError as e:
            # _LOG.exception(e)
            err_msg = f'Callbacks: {e} but going fallback to /test-plans/on-change/completed'
            _LOG.error(err_msg)
            planner.send_callback('/test-plans/on-change/completed', test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
            return

    if not context['test_preparations'][test_plan_uuid]['augmented_descriptors'] and not err_msg:
        # No correct test executions, sending callback
        err_msg = f'Curator was not able to setup any of the test environments for {test_plan_uuid}, ' \
                  f'sending callback to planner'
        _LOG.warning(err_msg)
        try:
            callback_path = [
                d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                if d['status'] == 'COMPLETED'
            ][0]
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
            return
        except AttributeError as e:
            # _LOG.exception(e)
            err_msg = f'Callbacks: {e} but going fallback to /test-plans/on-change/completed'
            _LOG.error(err_msg)
            planner.send_callback('/api/v1/test-plans/on-change/completed', test_plan_uuid, result_list=[], status='ERROR',
                                  exception=err_msg)
            return
    elif not context['test_preparations'][test_plan_uuid]['augmented_descriptors'] and err_msg:
        # Instantiation error
        _LOG.error(err_msg)
        try:
            callback_path = [
                d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                if d['status'] == 'COMPLETED'
            ][0]
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
            return
        except AttributeError as e:
            # _LOG.exception(e)
            err_msg = f'Callbacks: {e} but going fallback to /test-plans/on-change/completed'
            _LOG.error(err_msg)
            planner.send_callback('/api/v1/test-plans/on-change/completed', test_plan_uuid, result_list=[],
                                  status='ERROR',
                                  exception=err_msg)
            return

    elif context['test_preparations'][test_plan_uuid] and err_msg:
        _LOG.error('Triggering unknown failure process')
        callback_path = [
            d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
            if d['status'] == 'COMPLETED'
        ][0]
        planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
        return

    elif err_msg:
        # _LOG.error(f"{context['test_preparations'][test_plan_uuid]['augmented_descriptors']}{err_msg}")
        try:
            callback_path = [
                d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                if d['status'] == 'COMPLETED'
            ][0]
            planner.send_callback(callback_path, test_plan_uuid, result_list=[], status='ERROR', exception=err_msg)
            return
        except AttributeError as e:
            # _LOG.exception(e)
            err_msg = f'Callbacks: {e} but going fallback to /test-plans/on-change/completed'
            _LOG.error(err_msg)
            planner.send_callback('/api/v1/test-plans/on-change/completed', test_plan_uuid, result_list=[],
                                  status='ERROR',
                                  exception=err_msg)
            return

    elif all([
        test['test_status'] == 'COMPLETED'
        or test['test_status'] == 'ERROR'
        or test['test_status'] == 'CANCELLED'
        for test in context['test_preparations'][test_plan_uuid]['augmented_descriptors']
    ]):
        try:
            callback_path = [
                d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
                if d['status'] == 'COMPLETED'
            ][0]
            results = [test.get('test_results') for test in context['test_preparations'][test_plan_uuid]]
            planner.send_callback(callback_path, test_plan_uuid, result_list=results, status='ERROR', exception=err_msg)
            return
        except AttributeError as e:
            # _LOG.exception(e)
            err_msg = f'Callbacks: {e} but going fallback to /test-plans/on-change/completed'
            _LOG.error(err_msg)
            planner.send_callback('/api/v1/test-plans/on-change/completed', test_plan_uuid, result_list=[], status='ERROR',
                                  exception=err_msg)
            return

    else:
        # Shouldn't reach here, check why it did
        _LOG.error(f'Should not reach this point, check why app did it. Test_plan: #{test_plan_uuid}')
        _LOG.debug(f'var_trace:{vars()}')
        callback_path = [
            d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
            if d['status'] == 'COMPLETED'
        ][0]
        results = [
            context['test_preparations'][test_plan_uuid]['test_results'][test]
            for test in context['test_preparations'][test_plan_uuid]['test_results']
        ]
        planner.send_callback(callback_path, test_plan_uuid, result_list=results, status='ERROR')
        return
    # LOG.debug('completed ' + test_plan)


def clean_environment(test_plan_uuid, test_id=None, content=None, error=None):
    _LOG.info(f'Test {test_id} from test-plan {test_plan_uuid} finished')
    _LOG.debug(f'Callback content: {content}')
    platform_adapter = context['plugins']['platform_adapter']
    remote_docker_interface = context['test_preparations'][test_plan_uuid].get('docker_interface')
    if not remote_docker_interface:
        dockeri = context['plugins']['docker']
    else:
        dockeri = remote_docker_interface
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
            test_finished[1]['nsi_uuid'],
            test_finished[1]["package_uploaded"]
        )
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
                if not probe['id'].startswith('aa-bb-cc-dd'):
                    dockeri.rm_image(probe['image'])
            except Exception as e:
                tb = "".join(traceback.format_exc().split("\n"))
                _LOG.error(f'Failed removal of {probe["name"]}, reason: {e}, traceback: {tb}')
        try:
            # Do network prune
            dockeri.network_prune()
        except Exception as e:
            tb = "".join(traceback.format_exc().split("\n"))
            _LOG.error(f'Failed removal of {probe["name"]}, reason: {e}, traceback: {tb}')

        #  Answer to planner
        try:
            res_list = [
                {
                    'test_uuid': d['test_uuid'],
                    'test_result_uuid': d['results_uuid'],
                    'test_status': d['status']
                }
                for d in context['test_preparations'][test_plan_uuid]['test_results'] if d is not None
            ]
            if all([res['test_status'] == 'COMPLETED' for res in res_list]):
                final_status = 'COMPLETED'
            else:
                final_status = 'ERROR'
            _LOG.debug(f'results for test_plan #{test_plan_uuid}: {res_list}')
            planner_resp = planner.send_callback(callback_path, test_plan_uuid, res_list, status=final_status, exception=error)
            _LOG.debug(f'Response from planner: {planner_resp}')
            # if planner_resp ok, clean test_preparations entry
            if remote_docker_interface:
                dockeri.close()
            del context['test_preparations'][test_plan_uuid]
        except Exception as e:
            tb = "".join(traceback.format_exc().split("\n"))
            _LOG.error(f'Error during test_results recovery: {tb}')
            planner_resp = planner.send_callback(callback_path, test_plan_uuid, [], status='ERROR', exception=tb)
            _LOG.debug(f'Response from planner (Errback): {planner_resp}')


def test_status_update(test_plan_uuid, test_id, content):
    pass


def execute_test_plan():
    # TODO: execute tests inside test_plan
    # For the moment we have only 1 test per test_plan
    pass


def cancel_test_plan(test_plan_uuid):
    """
    Cancel all running tests on that test_bundle
    and return response to planner
    :param test_plan_uuid:
    :param content:
    :return:
    """
    _LOG.info(f'Canceling test-plan {test_plan_uuid} by planner request')
    planner = context['plugins']['planner']
    executor = context['plugins']['executor']
    platform_adapter = context['plugins']['platform_adapter']
    remote_docker_interface = context['test_preparations'][test_plan_uuid].get('docker_interface')
    if not remote_docker_interface:
        dockeri = context['plugins']['docker']
    else:
        dockeri = remote_docker_interface
    try:
        callback_path = [
            d['url'] for d in context['test_preparations'][test_plan_uuid]['test_plan_callbacks']
            if d['status'] == 'COMPLETED'
        ][0]
    except AttributeError as e:
        # _LOG.exception(e)
        _LOG.error(f'Callbacks: {e} but going forward')
        callback_path = ''
    # Cancel running tests
    try:
        for test in [run_test for run_test in context['test_preparations'][test_plan_uuid]['augmented_descriptors']
                     if run_test['test_status'] == 'RUNNING' or run_test['test_status'] == 'STARTING']:
            context['events'][test_plan_uuid][test['test_uuid']] = threading.Event()
            _LOG.debug(f'Cancelling test #{test["test_uuid"]}')
            executor.execution_cancel(test_plan_uuid, test['test_uuid'])
            context['events'][test_plan_uuid][test['test_uuid']].wait()
            del context['events'][test_plan_uuid][test['test_uuid']]
            # clean service platform
            _LOG.debug(f'Cleaning up test #{test["test_uuid"]} environment')
            pa_termination_response = platform_adapter.shutdown_package(
                context['events'][test_plan_uuid][test['test_uuid']]['platform']['name'],
                context['events'][test_plan_uuid][test['test_uuid']]['nsi_uuid'],
                context['events'][test_plan_uuid][test['test_uuid']]['package_uploaded']
            )
            _LOG.debug(f'Test #{test["test_uuid"]}: Termination response from PA: {pa_termination_response}')

        _LOG.debug(f'Finished cancellation for test-plan {test_plan_uuid}, '
                   f'cleaning up and sending results to planner')

    except Exception as e:
        tb = "".join(traceback.format_exc().split("\n"))
        _LOG.error(f'Error during test_results recovery: {tb}')
        res_list = [
            {
                'test_uuid': d['test_uuid'],
                'test_result_uuid': d['results_uuid'],
                'test_status': d['status']
            }
            for d in context['test_preparations'][test_plan_uuid]['test_results'] if d is not None
        ]
        planner_resp = planner.send_callback(callback_path, test_plan_uuid, res_list, status='ERROR', exception=tb)
        _LOG.debug(f'Response from planner (Errback): {planner_resp}')

    # Remove probe images
    if 'probes' in context['test_preparations'][test_plan_uuid]:
        for probe in context['test_preparations'][test_plan_uuid]['probes']:
            try:
                _LOG.debug(f'Removing {probe["name"]}')
                dockeri.rm_image(probe['image'])
            except Exception as e:
                _LOG.exception(f'Failed removal of {probe["name"]}, reason: {e}')
    else:
        _LOG.warning(f'No probes for test plan {test_plan_uuid}')


    res_list = [
        {
            'test_uuid': d['test_uuid'],
            'test_result_uuid': d['results_uuid'],
            'test_status': d['status']
        }
        for d in context['test_preparations'][test_plan_uuid]['test_results'] if d is not None
    ]

    #  Callback to planner
    planner_resp = planner.send_callback(callback_path, test_plan_uuid, res_list, status='CANCELLED')
    # if planner_resp ok, clean test_preparations entry
    if remote_docker_interface:
        dockeri.close()
    _LOG.debug(f'Response from planner: {planner_resp}')
    del context['test_preparations'][test_plan_uuid]
    _LOG.debug(f'Finished cancellation of {test_plan_uuid}')


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
                if type(probe_param['value']) == str and probe_param['value'].startswith('$(') and probe_param['value'].endswith(')'):
                    path = probe_param['value'].strip('$()').split('/')
                    for parameter in instantiation_parameters:
                        if parameter['name'] == path[0]:
                            value = route_from_text(parameter, path[1:])
                            probe_param['value'] = value
                            break
            not_parsed = [param['value'] for param in probe['parameters'] if param['value'].startswith('$(')]
            if not_parsed:
                raise ValueError(f'Some probe parameters are not well referenced, {not_parsed}')



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

