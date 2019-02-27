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

import os
import requests


class Client:
    """
    Client Abstraction WIP
    """
    def __init__(self):
        self.base_url = ''
        self.ledger = []


class PlannerClient(Client):
    """
    This is a client for Planner
    """
    def __init__(self):
        Client.__init__(self)
        self.base_url = os.getenv('platform_adapter_base')


class PlatformAdapterClient(Client):
    """
    This is a client for Platform Adapter
    """
    def __init__(self):
        Client.__init__(self)
        self.base_url = os.getenv('platform_adapter_base')

    def instantiate_package_sonata(self, uuid):
        """
        POST /tng-vnv-platform-mngr/adapters/<service_platform>/instantiations
            {
                "service_uuid":"86970b5e-0064-457e-b145-22ff13e08f65"
            }
        :param platform:
        :param uuid:
        :return:
        """
        url = '/'.join([self.base_url, 'test-executions', 'sonata', 'cancel'])

    def instantiate_package_osm(self, ):
        """
        POST tng-vnv-platform-mngr/adapters/<service_platform>/instantiations
        {
            "nsd_name" : "test_nsd",
            "ns_name" : "test_ns",
            "vim_account" : "OS127",
            "callback": "http://my_callback_url:6666" (OPTIONAL)
        }
        :param platform:
        :param uuid:
        :return:
        """
        url = '/'.join([self.base_url, 'test-executions', 'osm', 'cancel'])

    def shutdown_package(self, platform, package_uuid):
        url

    def upload_package(self, platform, package_uuid, package_object):
        if platform == 'osm':
            pass
        elif platform == 'sonata':
            url = '/'.join([self.base_url, 'tng-vnv-platform-mngr', 'adapters', platform, 'packages'])


    def delete_package(self, platform, package_uuid, name=None, vendor=None, version=None):
        if platform == 'osm':
            pass
        elif platform == 'sonata':
            if not (name and vendor and version):
                # Get packages and filter by uuid offline, asign to vars
                name = str()
                vendor = str()
                version = str()

            url = '/'.join([self.base_url, 'tng-vnv-platform-mngr', 'adapters', platform, 'packages',
                            name, vendor, version])
            response = requests.delete(url)


class CatalogueClient(Client):
    """
    This is a client class for V&V catalogue
    """
    def __init__(self):
        Client.__init__(self)
        self.base_url = os.getenv('platform_adapter_base')
        self.VERSION = 'v2'

    def get_package(self,):
        url = '/'.join([self.base_url, 'api', 'catalogues', self.VERSION, 'packages'])


class ExecutorClient(Client):
    """
    This is a client class for V&V Executor
    """
    def __init__(self):
        Client.__init__(self)
        self.base_url = os.getenv('executor_base')

    def execution_request(self):
        url = '/'.join([self.base_url, 'test-executions'])

    def execution_cancel(self, test_uuid):
        url = '/'.join([self.base_url, 'test-executions', test_uuid, 'cancel'])
