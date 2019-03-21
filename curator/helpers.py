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
import logging
import threading
from curator.database import context
import curator.interfaces.vnv_components_interface as vnv_i
import curator.interfaces.common_databases_interface as db_i
import curator.interfaces.docker_interface as dock_i
from time import sleep


_LOG = logging.getLogger('flask.app')


def process_test_plan(test_bundle_uuid, nsi_event):
    _LOG.info(f'Processing {test_bundle_uuid}')
    # test_plan contains NSD and TD
    td = context['test_preparations'][test_bundle_uuid]['test_descriptor']
    nsd = context['test_preparations'][test_bundle_uuid]['network_service_descriptor']
    context['test_preparations'][test_bundle_uuid]['augmented_descriptors'] = []
    planner = context['plugins']['planner']
    dockeri = context['plugins']['docker']
    dockeri = dock_i.DockerInterface()
    # planner = vnv_i.PlannerInterface()
    planner.add_new_test_plan(test_bundle_uuid)
    platforms = td['service_platforms']  # should be a list
    platform_adapter = context['plugins']['platform_adapter']
    executor = context['plugins']['executor']
    vnv_cat = context['plugins']['catalogue']
    context['test_preparations'][test_bundle_uuid]['probes'] = []
    configuration_phase = [phase for phase in td['phases'] if phase['action'] == 'configure'].pop()
    for probe in configuration_phase['probes']:
        image = dockeri.pull(probe['image'])
        context['test_preparations'][test_bundle_uuid]['probes'].append(
            {
                'id': image.short_id,
                'name': probe['name'],
                'image': probe['image']
            }
        )
    if type(platforms) is list:

        # Network service deployment, for each test
        for platform_type in platforms:
            _LOG.info(f'Accesing {platform_type}')
            if platform_type == 'SONATA':
                service_platform = platform_adapter.available_platforms_by_type(platform_type.lower())[0]
                # (jdelacruz) Until (vendor, name, version) is assured to be the same for the package than for
                # the nsd, I am keeping this previous block
                _LOG.debug('Search package for nsd {vendor}:{name}:{version}'.format(**nsd))
                package_info = vnv_cat.get_package_id_from_nsd_tuple(
                    nsd['vendor'], nsd['name'], nsd['version'])
                # _LOG.debug(f'Matching package found {package_info["uuid"]}, transfer to {service_platform["name"]}')
                _LOG.debug(f'Matching package found {package_info["uuid"]}, '
                           f'instantiating in {service_platform["name"]}')
                instance_name = f"test-{td['name']}-{package_info['name']}-{service_platform}"
                context['events'][instance_name] = threading.Event()
                inst_result = platform_adapter.automated_instantiation_sonata(
                    service_platform['name'],
                    package_info['name'], package_info['vendor'], package_info['version'],
                    instance_name=instance_name,
                    test_plan_uuid=test_bundle_uuid
                )
                if inst_result['error']:
                    raise Exception(inst_result['error'])
                context['events'][instance_name].set()
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
                context['events'][instance_name].wait()
                instantiation_params = [augd['functions'] for augd in context['test_preparations'][test_bundle_uuid]['augmented_descriptors'] if augd['platform'] == platform_type.lower()][0]
                # TODO: parse parameters into TD
                # platform_adapter.get_service_instantiation()
                # instantiation_params = {
                #     'destination': '1.2.3.4',
                #     'port': '123'
                # }
                test_descriptor_instance = generate_test_descriptor_instance(td, instantiation_params)
                executor.execution_request()
                url = 'http://tng-vnv-executor:6102/test-executions'

                _LOG.debug('Response from executor: {}'.format(response))
            elif platform_type == 'OSM':
                # TODO
                sp = platform_adapter.available_platforms_by_type(platform_type.lower())[0]
                pass
            elif platform_type == 'ONAP':
                # TODO
                pass
            else:
                raise NotImplementedError(f'Platform {platform_type} is not compatible')
    else:
        _LOG.error(f'Wrong platform value, should be a list and is a {type(platforms)}')
    # LOG.debug('completed ' + test_plan)


def execute_test_plan():
    # TODO: execute tests inside test_plan
    pass


def cancel_test_plan(test_plan_uuid, callback=None):
    planner = context['plugin']['planner']
    executor = context['plugin']['executor']
    if callback:
        planner.send_callback(callback) #, payload)
        test_uuid_list = [test['uuid'] for test in context['test_plan_uuid']['tests'] if test['status'] == 'RUNNING']
        for test_uuid in test_uuid_list:
            executor.execution_cancel(test_uuid)
    else:
        raise ValueError('No callback')


def generate_test_descriptor_instance(test_descriptor, parameters):
    #  Shake it and deliver
    test_descriptor_instance = {
        'new': 'test',
        'callbacks': {
            'finish': '/api/v1/test-preparations/<test_bundle_uuid>/tests/<test_uuid>/finish'
        }
    }
    return test_descriptor_instance


def wait_for_instatiation(platform_adapter, service_platform, service_uuid, period=5, timeout=None):
    """

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

