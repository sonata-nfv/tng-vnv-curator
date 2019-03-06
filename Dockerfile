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


FROM python:3.6-slim
LABEL organization=5GTANGO


# Configuration

# Catalogue information
ENV cat_base http://tng-cat:4011/

# Platform Adapter
ENV platform_adapter_base http://tng-vnv-platform-adapter:5001/

ENV planner_base http://tng-vnv-planner:6100/

ENV executor_base http://tng-vnv-executor:6300/

# Install dependencies (system level)
RUN apt update && apt install -y glpk-utils python3-pip libffi-dev libssl-dev git
#RUN python -m pip install --upgrade pip setuptools wheel
# RUN pip install requirements.txt

# add plugin related files
WORKDIR /
ADD README.md /tng-vnv-curator/
#ADD requirements.txt  /tng-vnv-curator/
ADD setup.py  /tng-vnv-curator/

# install actual plugin
WORKDIR /tng-vnv-curator
RUN python setup.py develop

ADD .  /tng-vnv-curator

#CMD ["tng-vnv-curator"]
CMD ["python", "-c",  "import flask"]