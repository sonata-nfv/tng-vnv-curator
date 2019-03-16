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
from curator.database import context
import curator.interfaces.vnv_components_interface as vnv_i
import curator.interfaces.common_databases_interface as db_i


_LOG = logging.getLogger('flask.app')


def process_test_plan(test_bundle_uuid):
    _LOG.info(f'Processing {test_bundle_uuid}')
    # test_plan contains NSD and TD
    td = context['test_preparations'][test_bundle_uuid]['test_descriptor']
    nsd = context['test_preparations'][test_bundle_uuid]['network_service_descriptor']

    planner = context['plugins']['planner']
    planner = vnv_i.PlannerInterface()
    planner.add_new_test_plan(test_bundle_uuid)
    platforms = td['service_platforms']  # should be a list
    platform_adapter = context['plugins']['platform_adapter']
    vnv_cat = context['plugins']['catalogue']
    if type(platforms) is list:

        # Network service deployment
        for platform_type in platforms:
            _LOG.info(f'Accesing {platform_type}')
            if platform_type == 'SONATA':
                service_platform = platform_adapter.available_platforms_by_type(platform_type.lower())[0]
                _LOG.debug('Search package for nsd {vendor}:{name}:{version}'.format(**nsd))
                package_info = vnv_cat.get_package_id_from_nsd_tuple(
                    nsd['vendor'], nsd['name'], nsd['version'])
                _LOG.debug(f'Matching package found {package_info}, transfer to {service_platform["name"]}')
                sp_package_process_uuid = platform_adapter.transfer_package_sonata(
                    package_info, service_platform['name'])
                sp_network_service = platform_adapter.get_service_uuid_sonata(
                    service_platform['name'],
                    nsd['name'], nsd['vendor'], nsd['version'])
                _LOG.debug(f'Remote NS is {sp_network_service}, instantiating')
                sp_response = platform_adapter.instantiate_service_sonata(
                    service_platform['name'], sp_network_service, td['name'])
                if sp_response['error']:
                    raise ConnectionError(sp_response['error'])
                else:
                    _LOG.info(f'NS {sp_network_service} instantiated')
                # TODO: get NS parameters
                # TODO: parse parameters into TD






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

    # Pull docker images
    context['test-preparations'][test_bundle_uuid] = td
    instantiation_params = {
        'destination': '1.2.3.4',
        'port': '123'
    }
    test_descriptor_instance = generate_test_descriptor_instance(td, instantiation_params)
    url = 'http://tng-vnv-executor:6102/test-executions'
    response = requests.post(url,json=test_descriptor_instance)
    _LOG.debug('Response from executor: {}'.format(response))
    # LOG.debug('completed ' + test_plan)


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


def generate_test_descriptor_instance(test_plan, parameters):
    #  Shake it and deliver
    test_descriptor_instance = {'new': 'test'}
    # Add callbacks
    test_descriptor_instance['callbacks'] = {
        'finish': '/api/v1/test-preparations/<test_bundle_uuid>/tests/<test_uuid>/finish'
    }
    return test_descriptor_instance


def sonata_workflow():

    def get_package():
        pass

    def instantiate_package():
        pass





def osm_workflow():

    def instantiate_nsd():
        pass

    def tear_down_nsd():
        pass
    pass


def onap_workflow():

    def get_package():
        pass

    def instantiate_nsd():
        pass

    def tear_down_nsd():
        pass
    pass
