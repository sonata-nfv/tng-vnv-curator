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
import logging
import json
from curator.interfaces.interface import Interface
from curator.database import context
from curator.logger import TangoLogger

# _LOG = TangoLogger.getLogger('flask.app', log_level=logging.DEBUG, log_json=True)
_LOG = logging.getLogger('flask.app')


class PlannerInterface(Interface):
    """
    This is a Interface for Planner
    Callbacks: [
            {
                eventActor: 'Curator',
                url: '/test-plans/on-change/completed',
                status:TEST_PLAN_STATUS.COMPLETED,
            },
            {
                eventActor: 'Curator',
                url: '/test-plans/on-change’,
            }
        ]
    """
    def __init__(self, cu_api_root, cu_api_version):
        Interface.__init__(self, cu_api_root, cu_api_version)
        self.__base_url = os.getenv('planner_base')
        self.__running_test_plans = []

    def add_new_test_plan(self, test_plan_uuid):
        self.__running_test_plans.append(test_plan_uuid)

    def send_callback(self, suffix, test_plan_uuid, result_list, status='UNKNOWN', event_actor='Curator'):
        url = self.__base_url + suffix
        payload = {
            'event_actor': event_actor,
            'test_plan_uuid': test_plan_uuid,
            'status': status,
            'test_results': result_list
        }
        headers = {"Content-type": "application/json"}

        _LOG.debug(f'Accesing {url}')
        _LOG.debug(f'Payload {payload}')
        try:
            r = requests.post(url, headers=headers, json=payload)
            _LOG.debug(f'ResContent {r.text}'.replace('\n', ' '))
            _LOG.debug(f'ResHeaders {r.headers}')
            # resp = r.json()  # Response should be None
            if r.status_code == 200:
                return r.status_code
            else:
                return r
        except Exception as e:
            resp = {'error': str(e), 'content': None}
        return resp


class PlatformAdapterInterface(Interface):
    """
    This is a Interface for Platform Adapter (PA)
    """
    def __init__(self, cu_api_root, cu_api_version):
        Interface.__init__(self, cu_api_root, cu_api_version)
        self.base_url = os.getenv('platform_adapter_base')
        self.running_instances = []
        self.events = []

    def available_platforms(self):
        url = '/'.join([self.base_url, 'service_platforms'])
        headers = {"Content-type": "application/json"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def available_platforms_by_type(self, sp_type):
        url = '/'.join([self.base_url, 'service_platforms'])
        headers = {"Content-type": "application/json"}
        try:
            _LOG.debug(f'Getting {url}')
            response = requests.get(url, headers=headers)
            _LOG.debug(f'Response {response.json()}')
            if response.status_code == 200:
                return list(filter(lambda x: x['type'] == sp_type, response.json()))
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def remote_download_package(self, package_id):
        """
        Command the PA to download the package on his volume
        ref=https://github.com/sonata-nfv/tng-vnv-platform-adapter/wiki/curator#
        tng-vnv-platform-mngradapterspackagespackage_iddownload
        :param package_id:
        :return:
        """
        url = '/'.join([self.base_url, 'adapters', 'packages', package_id, 'download'])
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.text  # FIXME: Should be a json
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def transfer_package_sonata(self, package_info, service_platform):
        _LOG.debug(f'Start transfer of {package_info["uuid"]}@VnV(self) TO {service_platform}')
        self.remote_download_package(package_info["uuid"])
        package_process_uuid = self.upload_package(service_platform, package_info["package_file_uuid"])
        _LOG.debug(f'Transfer complete, running {package_process_uuid}@SP_({service_platform})')
        return package_process_uuid

    def transfer_package_osm(self):
        """
        Understanding package as the bundle of nsd + related vnfds
        :return:
        """
        pass

    def get_service_uuid_sonata(self, service_platform, name, vendor, version):
        """
        /adapters/<service_platform>/services/<:name>/<:vendor>/<:version>/id
        :param service_platform:
        :param name:
        :param vendor:
        :param version:
        :return:
        """
        url = '/'.join([self.base_url, 'adapters', service_platform, 'services',
                        name, vendor, version, 'id'])
        headers = {"Content-type": "application/json"}
        try:
            response = requests.post(url, headers=headers)
            if response.status_code == 200:
                return response.text
                # return response.json()  # FIXME: Every request should respond a JSON
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def get_service_instantiations_inventory(self, service_platform):
        """
        Returns a list of instantiated services
        {
           "id":"4537e905-5183-4d96-bb31-3860121e21df",
           "created_at":"2019-03-20T20:31:57.564Z",
           "updated_at":"2019-03-20T20:40:48.515Z",
           "status":"READY",
           "request_type":"CREATE_SERVICE",
           "instance_uuid":"143f50a9-ea11-4292-bd25-c0d4cbdabe6f",
           "ingresses":"[]",
           "egresses":"[]",
           "callback":"",
           "blacklist":"[]",
           "customer_uuid":null,
           "sla_id":null,
           "name":null,
           "error":null,
           "description":null,
           "service":{
              "uuid":"c8dfa216-c1bd-46da-ac8a-fa3fb444cc16",
              "vendor":"eu.5gtango",
              "name":"ns-squid-haproxy",
              "version":"0.2"
           }
        }
        :param service_platform:
        :return:
        """
        url = '/'.join([self.base_url, 'adapters', service_platform, 'instantiations'])
        headers = {"Content-type": "application/json"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def get_service_instantiation(self, service_platform, service_uuid):
        """
        Returns a instantiated service
        {
           "id":"4537e905-5183-4d96-bb31-3860121e21df",
           "created_at":"2019-03-20T20:31:57.564Z",
           "updated_at":"2019-03-20T20:40:48.515Z",
           "status":"READY",
           "request_type":"CREATE_SERVICE",
           "instance_uuid":"143f50a9-ea11-4292-bd25-c0d4cbdabe6f",
           "ingresses":"[]",
           "egresses":"[]",
           "callback":"",
           "blacklist":"[]",
           "customer_uuid":null,
           "sla_id":null,
           "name":null,
           "error":null,
           "description":null,
           "service":{
              "uuid":"c8dfa216-c1bd-46da-ac8a-fa3fb444cc16",
              "vendor":"eu.5gtango",
              "name":"ns-squid-haproxy",
              "version":"0.2"
           }
        }
        :param service_platform:
        :param service_uuid:
        :return:
        """
        url = '/'.join([self.base_url, 'adapters', service_platform, 'instantiations', service_uuid])
        headers = {"Content-type": "application/json"}
        _LOG.debug(f'Accesing {url}')
        try:
            response = requests.get(url, headers=headers)
            _LOG.debug(f'ResContent {response.text}')
            _LOG.debug(f'ResHeaders {response.headers}')
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def instantiate_service_sonata(self, service_platform, service_uuid,
                                   name, test_plan_uuid, test_uuid):
        """
        **************************************************
        ** DEPRECATED BY automated_instantiation_sonata **
        **************************************************
        POST /tng-vnv-platform-mngr/adapters/<service_platform>/instantiations
            {
                "service_uuid":"86970b5e-0064-457e-b145-22ff13e08f65"
            }

        IS SYNCHRONOUS

        EXAMPLE GOOD RESP:
        {
            "id":"4537e905-5183-4d96-bb31-3860121e21df", <- id in /adapters/qual-sp-bcn/instantiations/4537e905-5183-4d96-bb31-3860121e21df
            "created_at":"2019-03-20T20:31:57.564Z",
            "updated_at":"2019-03-20T20:31:57.564Z",
            "status":"NEW",
            "request_type":"CREATE_SERVICE",
            "instance_uuid":null, <- instance_uuid is nsr
            "ingresses":"[]",
            "egresses":"[]",
            "callback":"",
            "blacklist":"[]",
            "customer_uuid":null,
            "sla_id":null,
            "name":null,
            "error":null,
            "description":null,
            "service":{
                "uuid":"c8dfa216-c1bd-46da-ac8a-fa3fb444cc16",
                "vendor":"eu.5gtango",
                "name":"ns-squid-haproxy",
                "version":"0.2"
            }
        }
        EXAMPLE BAD RESP:
        {"error": "Error saving request"}
        :param platform:
        :param uuid:
        :return: dictionary
        """
        headers = {"Content-type": "application/json"}
        url = '/'.join([self.base_url, 'adapters', service_platform, 'instantiations'])
        data = {
            "service_uuid": service_uuid,
            "name": name,
            "callback": '/'.join(['http:/', context['host'], self.own_api_root, self.own_api_version,
                                  'test-preparations', test_plan_uuid, 'tests', test_uuid, 'sp-ready'])
        }
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def automated_instantiation_sonata(self, service_platform,
                                       service_name, service_vendor, service_version,
                                       instance_name, test_plan_uuid):
        """
        Simpler version to instantiate a service, working for sonata
        :param service_platform:
        :param service_name:
        :param service_vendor:
        :param service_version:
        :param instance_name:
        :param callback:
        :return: network_service
        """
        data = {
            "service_name": service_name,
            "service_vendor": service_vendor,
            "service_version": service_version,
            "service_platform": service_platform,
            "instance_name": instance_name,
            "callback": '/'.join([
                'http:/', context['host'],
                self.own_api_root, self.own_api_version,
                'test-preparations', test_plan_uuid,
                'service-instances', instance_name, 'sp-ready'])
        }
        _LOG.debug(f'Instantiation payload: {data}')
        url = '/'.join([self.base_url, 'adapters', 'instantiate_service'])
        _LOG.debug(f'Accesing {url}')
        headers = {"Content-type": "application/json"}
        try:
            response = requests.post(url, headers=headers, json=data)
            _LOG.debug(f'Response {response.text}'.replace('\n', ' '))
            if response.status_code == 200 and not response.json()['error']:
                return response.json()
            elif response.json()['error']:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError(response.json)
            else:
                raise Exception(response.json())
        except Exception as e:
            _LOG.exception(e)
            raise e

    def instantiate_service_osm(self, service_platform, nsd_name, ns_name, vim_account, instance_name):
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
        url = '/'.join([self.base_url, 'adapters', service_platform, 'instantiations'])

    def shutdown_package(self, service_platform, instance_uuid):
        """
        Shutdowns the instance and removes the package from the SP
        :param service_platform:
        :param instance_uuid:
        :return:
        """
        # url = '/'.join([self.base_url, 'adapters', service_platform, 'instantiations'])
        url = '/'.join([self.base_url, 'adapters', service_platform, 'instantiations', 'terminate'])

        data = {"instance_uuid": instance_uuid, "request_type": "TERMINATE_SERVICE"}
        headers = {"Content-type": "application/json"}
        try:
            _LOG.debug(f'Accesing {url}')
            _LOG.debug(f'Payload {data}')
            response = requests.post(url, headers=headers, json=data)
            _LOG.debug(f'ResContent {response.text}'.replace('\n', ' '))
            _LOG.debug(f'ResHeaders {response.headers}')
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def upload_package(self, platform, package_file_uuid):
        """
        {"package_process_uuid":"8f3a26b6-34e4-45e4-b7a3-17f6c5a55820","status":"running","error_msg":null}
        :param platform:
        :param package_uuid:
        :return:
        """
        url = '/'.join([self.base_url, 'adapters', platform, 'packages'])
        data = {"package": f"/app/packages/{package_file_uuid}.tgo"}
        headers = {"Content-type": "application/json"}
        try:
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def delete_package_sonata(self, service_platform, package_uuid, name=None, vendor=None, version=None):
        # if not (name and vendor and version):
        #     # Get packages and filter by uuid offline, asign to vars
        #     package_inventory_url = '/'.join([self.base_url, 'adapters', service_platform, 'packages'])
        #     response = requests.get()
        #
        #     name = str()
        #     vendor = str()
        #     version = str()
        url = '/'.join([self.base_url, 'adapters', service_platform, 'packages',
                        name, vendor, version])
        response = requests.delete(url)

    def get_inventory(self, platform):
        url = '/'.join([self.base_url, 'adapters', platform, 'packages'])


class ExecutorInterface(Interface):
    """
    This is a Interface class for V&V Executor
    """
    def __init__(self, cu_api_root, cu_api_version):
        Interface.__init__(self, cu_api_root, cu_api_version)
        self.base_url = os.getenv('executor_base')
        self.version = 'v1'
        self.api = 'api'
        self.events = []

    def execution_request(self, tdi, test_plan_uuid):
        """

        :param tdi:
        :param test_plan_uuid:
        :return:
        """
        # TODO: Specify content in the callbacks?
        data = {
            'test': tdi,
            "callbacks": [
                {
                    'name': 'running',
                    'path': '/'.join(
                        ['http:/', context['host'], self.own_api_root, self.own_api_version,
                         'test-preparations', test_plan_uuid, 'change'])
                },
                {
                    'name': 'cancel',
                    'path': '/'.join(
                        ['http:/', context['host'], self.own_api_root, self.own_api_version,
                         'test-preparations', test_plan_uuid, 'tests', '<test_uuid>', 'cancel'])
                },
                {
                    'name': 'finish',
                    'path': '/'.join(
                        ['http:/', context['host'], self.own_api_root, self.own_api_version,
                         'test-preparations', test_plan_uuid, 'tests', '<test_uuid>', 'finish'])
                }
            ]
        }
        url = '/'.join([self.base_url, self.api, self.version, 'test-executions'])
        headers = {"Content-type": "application/json"}
        _LOG.debug(f'Sending to executor {url} with payload {json.dumps(data)}')

        try:
            response = requests.post(url, headers=headers, json=data)
            _LOG.debug(f'Rstatus: {response.status_code}')
            _LOG.debug(f'Rdata: {response.content}')
            _LOG.debug(f'RESPONSE decoded: {response.json()}')
            if response.status_code == 202:  # and not response.json()['error']:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError(response.json())
            else:
                raise ValueError(f'Code not expected, {response.content}, status={response.status_code}')
        except Exception as e:
            _LOG.exception(e)
            raise e

    def execution_cancel(self, test_plan_uuid, test_uuid):
        data = {
            "callbacks": [
                {
                    'name': 'cancel',
                    'path': '/'.join(
                        ['http:/', context['host'], self.own_api_root, self.own_api_version,
                         'test-preparations', test_plan_uuid, 'tests', '<test_uuid>', 'cancel'])
                }
            ]
        }
        url = '/'.join([self.base_url, self.api, self.version, 'test-executions', test_uuid, 'cancel'])
        headers = {"Content-type": "application/json"}
        try:
            response = requests.post(url, headers=headers, json=data)
            _LOG.debug(f'Rstatus: {response.status_code}')
            _LOG.debug(f'Rdata: {response.raw}')
            if response.status_code == 200:  # and not response.json()['error']:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError(response.json())
            elif response.status_code == 500:
                raise RuntimeError('Server error ', response.content)
            else:
                raise ValueError(f'Code not expected, {response.content}, status={response.status_code}')
        except Exception as e:
            _LOG.exception(e)
            raise e

