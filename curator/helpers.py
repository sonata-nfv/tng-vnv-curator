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


def process_test_plan(app, test_bundle_uuid):
    app.logger.debug('Processing ' + test_bundle_uuid)
    # test_plan contains NSD and TD
    test_plan = context['test_preparations'][test_bundle_uuid]['test_plan']
    platforms = test_plan['service_platforms']  # should be a list
    if type(platforms) is not list:
        app.logger.error('Wrong platform value, should be a list and is a {}'.format(type(platforms)))
    else:
    # Network service deployment
        for platform in platforms:
            if platform is 'sonata':
                sonata_workflow()
            elif platform is 'OSM':
                osm_workflow()
            elif platform is 'ONAP':
                onap_workflow()
            else:
                raise NotImplementedError('Platform {} is not compatible')
    # Pull docker images
    context['test-preparations'][test_bundle_uuid] = test_plan
    instantiation_params = {
        'destination': '1.2.3.4',
        'port': '123'
    }
    test_descriptor_instance = generate_test_descriptor_instance(test_plan, instantiation_params)
    url = 'http://tng-vnv-executor:6102/test-executions'
    response = requests.post(url,json=test_descriptor_instance)
    app.logger.debug('Response from executor: {}'.format(response))
    # LOG.debug('completed ' + test_plan)


def cancel_test_plan(app, test_plan_uuid):
    pass


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
