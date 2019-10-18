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
# import yaml
import docker
import logging
from curator.interfaces.interface import Interface
from curator.database import context
from curator.logger import TangoLogger


_LOG = TangoLogger.getLogger('curator:docker', log_level=logging.DEBUG, log_json=True)
# _LOG = logging.getLogger('flask.app')


class DockerInterface(Interface):
    def __init__(self, execution_host=None):
        # connect to docker
        Interface.__init__(self)
        if not execution_host:
            # The default docker manager
            self.docker_manager = self.connect()
        else:
            # Remote docker manager
            docker_host = f'tcp://{execution_host}:2375'
            self.docker_manager = docker.client.DockerClient(docker_host)

    def connect(self):
        """
        Connect to a Docker service on which FSMs/SSMs shall be executed.
        The connection information for this service should be specified with the following
        environment variables (example for a docker machine installation):

            export DOCKER_TLS_VERIFY="1"
            export DOCKER_HOST="tcp://192.168.99.100:2376"
            export DOCKER_CERT_PATH="/Users/<user>/.docker/machine/machines/default"
            export DOCKER_MACHINE_NAME="default"

            Docker machine hint: eval $(docker-machine env default) sets all needed ENV variables.

        If DOCKER_HOST is not set, the default local Docker socket will be tried.
        :return: client object
        """
        if os.environ.get("DOCKER_HOST") is None:
            os.environ["DOCKER_HOST"] = "unix://var/run/docker.sock"
            _LOG.warning(f"ENV variable 'DOCKER_HOST' not set; using {os.environ['DOCKER_HOST']} as fallback")

        # lets connect to the Docker instance specified in current ENV
        # cf.: http://docker-py.readthedocs.io/en/stable/machine/
        client = docker.from_env(assert_hostname=False)
        # do a call to ensure that we are connected
#        dc.info()
#        LOG.info("Connected to Docker host: {0}".format(dc.base_url))
        return client

    def is_image_in_repository(self, image_name):
        try:
            self.docker_manager.images.get(image_name)
            return True
        except docker.errors.ImageNotFound as e:
            return False

    def get_image(self, image_name):
        try:
            image = self.docker_manager.images.get(image_name)
            return image
        except docker.errors.ImageNotFound as e:
            _LOG.error(f'Image {image_name} has been not found')
            return None

    def prune(self):
        pass

    def pull(self, image_name, retry_max=3):

        """
        Process of pulling a Docker image probe
        """
        # repository pull
        image = None
        retry_count = 0
        while not image:
            try:
                image = self.docker_manager.images.pull(image_name)  # image name and uri are the same
                _LOG.debug(f'Image id: {image.id}')
            except docker.errors.ImageNotFound as e:
                retry_count += 1
                if retry_count < retry_max:
                    #  LOG.debug('Image not found, retry {}'.format(retry_count))
                    pass
                else:
                    raise e
            finally:
                return image

    def rm_image(self, image):
        self.docker_manager.images.remove(image=image, force=True)

    def start(self, id, image, sm_type, uuid, p_key):
        # if 'network_id' in os.environ:
        #     network_id = os.environ['network_id']
        # else:
        #     network_id = 'sonata'
        #
        # vh_name = '{0}-{1}'.format(sm_type,uuid)
        # broker_host = "{0}/{1}".format(self.sm_broker_host, vh_name)
        #
        # cn_name = "{0}{1}".format(id,uuid)
        #
        # container = self.docker_manager.create_container(
        #     image=image,
        #     detach=True,
        #     name=cn_name,
        #     environment={'broker_host':broker_host, 'sf_uuid':uuid, 'PRIVATE_KEY':p_key})
        # networks = self.docker_manager.networks()
        # net_found = False
        # for i in range(len(networks)):
        #     if networks[i]['Name'] == network_id:
        #         net_found = True
        #         break
        #
        # if (net_found):
        #     _LOG.info('Docker network is used!')
        #     self.docker_manager.connect_container_to_network(container=container, net_id=network_id, aliases=[id])
        #     self.docker_manager.start(container=container.get('Id'))
        # else:
        #     _LOG.warning(f'Network ID: {network_id} Not Found!, deprecated Docker --link is used instead')
        #     self.docker_manager.start(container=container.get('Id'), links=[(broker['name'], broker['alias'])])
        pass

    def stop(self, ssm_name):
        self.docker_manager.kill(ssm_name)

    def rm(self, c_id, image, uuid):
        cn_name = f"{c_id}{uuid}"
        _LOG.info(f"{c_id} Logs: {self.docker_manager.logs(container=cn_name)}")
        self.docker_manager.stop(container=cn_name)
        self.docker_manager.remove_container(container=cn_name, force=True)
        self.docker_manager.remove_image(image=image, force=True)

    def close(self):
        self.docker_manager.close()
