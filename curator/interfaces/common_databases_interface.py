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
import shutil
from curator.interfaces.interface import Interface
# from curator.logger import TangoLogger


# _LOG = TangoLogger.getLogger('flask.app', log_level=logging.DEBUG, log_json=True)
_LOG = logging.getLogger('flask.app')


class CatalogueInterface(Interface):
    """
    This is a Interface class for V&V catalogue
    """
    def __init__(self):
        Interface.__init__(self)
        self.base_url = os.getenv('cat_base')
        self.VERSION = 'v2'

    def get_network_descriptor(self, network_uuid):
        url = '/'.join([self.base_url, 'api', self.VERSION,
                        'network-services', network_uuid])
        headers = {"Content-type": "application/json"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError(response.json()['error'])
        except Exception as e:
            _LOG.exception(e)
            raise e

    def get_network_descriptor_tuple(self, vendor, name, version):
        url = '/'.join([self.base_url, 'api', self.VERSION, 'network-services'])
        query = '?' + '&'.join([
            '='.join(['vendor', vendor]),
            '='.join(['name', name]),
            '='.join(['version', version]),
        ])
        _LOG.debug(f'GET {url}{query}')
        headers = {"Content-type": "application/json"}
        try:
            response = requests.get(url + query, headers=headers)
            _LOG.debug(f'RESP {response.content}')
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError(response.json()['error'])
        except Exception as e:
            _LOG.exception(e)
            raise e

    def get_test_descriptor(self, test_uuid):
        url = '/'.join([self.base_url, 'api', self.VERSION, 'tests', test_uuid])
        headers = {"Content-type": "application/json"}
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError(error=response.json()['error'])
        except Exception as e:
            _LOG.exception(e)
            raise e

    def get_test_descriptor_tuple(self, vendor, name, version):
        """

        :param vendor:
        :param name:
        :param version:
        :return:
        """
        url = '/'.join([self.base_url, 'api', self.VERSION, 'tests'])
        query = '?' + '&'.join([
            '='.join(['vendor', vendor]),
            '='.join(['name', name]),
            '='.join(['version', version]),
        ])
        headers = {"Content-type": "application/json"}
        _LOG.debug(f'GET {url}{query}')
        try:
            response = requests.get(url + query, headers=headers)
            _LOG.debug(f'RESP {response.content}')
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e

    def get_package_from_nsd_tuple(self, vendor, name, version):
        """
        Gets all packages, filter by package.nsd info (Vendor, Name, Version), returns package
        :param vendor:
        :param name:
        :param version:
        :return: {package}
        """
        package_inventory = self.get_package_descriptor_inventory()
        filtered_packages = [
            package['pd'] for package in package_inventory if [
                pd for pd in package['pd']['package_content']
                if pd['content-type'] == 'application/vnd.5gtango.nsd'
                and pd['id']['vendor'] == vendor
                and pd['id']['name'] == name
                and pd['id']['version'] == version
            ]
        ]
        if len(filtered_packages) > 1:
            raise Warning('More than one matching package: {}'.format(
                [p['package_file_uuid'] for p in filtered_packages]))
        elif len(filtered_packages) == 0:
            raise FileNotFoundError
        return filtered_packages[0]

    def get_package_id_from_nsd_tuple(self, vendor, name, version):
        """
        Gets all packages, filter by package.nsd info (Vendor, Name, Version), returns package id
        :param vendor:
        :param name:
        :param version:
        :return: package{'uuid', 'vendor', 'name', 'version',
                        'package_file_uuid', 'package_file_name'}
        """
        package_inventory = self.get_package_descriptor_inventory()
        filtered_packages = [
            package for package in package_inventory if [
                package_content for package_content in package['pd']['package_content']
                if package_content['content-type'] == 'application/vnd.5gtango.nsd'
                and package_content['id']['vendor'] == vendor
                and package_content['id']['name'] == name
                and package_content['id']['version'] == version
            ]
        ]
        if len(filtered_packages) > 1:
            raise Warning('More than one matching package: {}'.format(
                [p['uuid'] for p in filtered_packages]))
        elif len(filtered_packages) == 0:
            raise FileNotFoundError
        return {
            'uuid': filtered_packages[0]['uuid'],
            'vendor': filtered_packages[0]['pd']['vendor'],
            'name': filtered_packages[0]['pd']['name'],
            'version': filtered_packages[0]['pd']['version'],
            'package_file_uuid': filtered_packages[0]['pd']['package_file_uuid'],
            'package_file_name': filtered_packages[0]['pd']['package_file_name']
        }

    def get_package_descriptor_inventory(self):
        url = '/'.join([self.base_url, 'api', self.VERSION, 'packages'])
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

    def get_package_descriptor(self, package_uuid):
        """

        :param package_uuid:
        :return:
        """
        url = '/'.join([self.base_url, 'api', self.VERSION, 'packages', package_uuid])
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

    def get_tgo_package_binary(self, tgo_package_uuid, tgo_package_name):
        """
        http://tng-cat:4011/api/v2/tgo-packages/57fa27d4-d3ae-4e6a-a2a8-c89b32381269
        :param tgo_package_uuid:
        :param tgo_package_name:
        :return: path of the file
        """
        url = '/'.join([self.base_url, 'api', self.VERSION, 'tgo-packages', tgo_package_uuid])
        headers = {"Content-type": "application/json"}
        path = '/tmp/{}'.format(tgo_package_name)
        try:
            response = requests.get(url, headers=headers, stream=True)
            if response.status_code == 200:
                with open(path, 'wb') as f:
                    response.raw.decode_content = True
                    shutil.copyfileobj(response.raw, f)
                return path
            elif response.status_code == 404:
                raise FileNotFoundError
        except Exception as e:
            _LOG.exception(e)
            raise e
