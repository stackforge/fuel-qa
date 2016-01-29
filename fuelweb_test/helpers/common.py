#    Copyright 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time

from fuelweb_test import logger as LOGGER
from fuelweb_test import logwrap as LOGWRAP
from fuelweb_test.settings import DISABLE_SSL
from fuelweb_test.settings import PATH_TO_CERT
from fuelweb_test.settings import VERIFY_SSL

from cinderclient import client as cinderclient
from glanceclient.v1 import Client as GlanceClient
from keystoneclient.v2_0 import Client as KeystoneClient
from keystoneclient.exceptions import ClientException
from novaclient.v2 import Client as NovaClient
import neutronclient.v2_0.client as neutronclient
from proboscis.asserts import assert_equal
import ironicclient.client as ironicclient


class Common(object):
    """Common."""  # TODO documentation

    def __init__(self, controller_ip, user, password, tenant):
        self.controller_ip = controller_ip

        if DISABLE_SSL:
            auth_url = 'http://{0}:5000/v2.0/'.format(self.controller_ip)
            path_to_cert = None
        else:
            auth_url = 'https://{0}:5000/v2.0/'.format(self.controller_ip)
            path_to_cert = PATH_TO_CERT

        insecure = not VERIFY_SSL

        LOGGER.debug('Auth URL is {0}'.format(auth_url))
        nova_args = {'username': user, 'api_key': password,
                     'project_id': tenant, 'auth_url': auth_url,
                     'cacert': path_to_cert, 'insecure': insecure}
        cinder_args = {'version': 1, 'username': user,
                       'password': password, 'project_id': tenant,
                       'auth_url': auth_url, 'cacert': path_to_cert,
                       'insecure': insecure}
        neutron_args = {'username': user, 'password': password,
                        'tenant_name': tenant, 'auth_url': auth_url,
                        'ca_cert': path_to_cert, 'insecure': insecure}
        keystone_args = {'username': user, 'password': password,
                         'tenant_name': tenant, 'auth_url': auth_url,
                         'ca_cert': path_to_cert, 'insecure': insecure}

        self.nova = NovaClient(**nova_args)

        self.cinder = cinderclient.Client(**cinder_args)

        self.neutron = neutronclient.Client(**neutron_args)

        self.keystone = self._get_keystoneclient(**keystone_args)

        token = self.keystone.auth_token
        LOGGER.debug('Token is {0}'.format(token))
        glance_endpoint = self.keystone.service_catalog.url_for(
            service_type='image', endpoint_type='publicURL')
        LOGGER.debug('Glance endpoint is {0}'.format(glance_endpoint))

        glance_args = {'endpoint': glance_endpoint, 'token': token,
                       'cacert': path_to_cert, 'insecure': insecure}

        self.glance = GlanceClient(**glance_args)
        try:
            ironic_endpoint = self.keystone.service_catalog.url_for(
                service_type='baremetal',
                endpoint_type='publicURL')
            self.ironic = ironicclient.get_client(
                api_version=1,
                os_auth_token=token,
                ironic_url=ironic_endpoint, insecure=True)
        except ClientException as e:
            LOGGER.warning('Could not initialize ironic client {0}'.format(e))

    def goodbye_security(self):
        secgroup_list = self.nova.security_groups.list()
        LOGGER.debug("Security list is {0}".format(secgroup_list))
        secgroup_id = [i.id for i in secgroup_list if i.name == 'default'][0]
        LOGGER.debug("Id of security group default is {0}".format(
            secgroup_id))
        LOGGER.debug('Permit all TCP and ICMP in security group default')
        self.nova.security_group_rules.create(secgroup_id,
                                              ip_protocol='tcp',
                                              from_port=1,
                                              to_port=65535)
        self.nova.security_group_rules.create(secgroup_id,
                                              ip_protocol='icmp',
                                              from_port=-1,
                                              to_port=-1)

    def update_image(self, image, **kwargs):
        self.glance.images.update(image.id, **kwargs)
        return self.glance.images.get(image.id)

    def delete_image(self, image_id):
        return self.glance.images.delete(image_id)

    def create_key(self, key_name):
        LOGGER.debug('Try to create key {0}'.format(key_name))
        return self.nova.keypairs.create(key_name)

    def create_instance(self, flavor_name='test_flavor', ram=64, vcpus=1,
                        disk=1, server_name='test_instance', image_name=None,
                        neutron_network=True, label=None):
        LOGGER.debug('Try to create instance')

        start_time = time.time()
        while time.time() - start_time < 100:
            try:
                if image_name:
                    image = [i.id for i in self.nova.images.list()
                             if i.name == image_name]
                else:
                    image = [i.id for i in self.nova.images.list()]
                break
            except:
                pass
        else:
            raise Exception('Can not get image')

        kwargs = {}
        if neutron_network:
            net_label = label if label else 'net04'
            network = self.nova.networks.find(label=net_label)
            kwargs['nics'] = [{'net-id': network.id, 'v4-fixed-ip': ''}]

        LOGGER.info('image uuid is {0}'.format(image))
        flavor = self.nova.flavors.create(
            name=flavor_name, ram=ram, vcpus=vcpus, disk=disk)
        LOGGER.info('flavor is {0}'.format(flavor.name))
        server = self.nova.servers.create(
            name=server_name, image=image[0], flavor=flavor, **kwargs)
        LOGGER.info('server is {0}'.format(server.name))
        return server

    @LOGWRAP
    def get_instance_detail(self, server):
        details = self.nova.servers.get(server)
        return details

    def verify_instance_status(self, server, expected_state):
        def _verify_instance_state():
            curr_state = self.get_instance_detail(server).status
            assert_equal(expected_state, curr_state)

        try:
            _verify_instance_state()
        except AssertionError:
            LOGGER.debug('Instance is not {0}, lets provide it the last '
                         'chance and sleep 60 sec'.format(expected_state))
            time.sleep(60)
            _verify_instance_state()

    def delete_instance(self, server):
        LOGGER.debug('Try to delete instance')
        self.nova.servers.delete(server)

    def create_flavor(self, name, ram, vcpus, disk, flavorid="auto",
                      ephemeral=0):
        flavor = self.nova.flavors.create(name, ram, vcpus, disk, flavorid,
                                          ephemeral=ephemeral)
        return flavor

    def delete_flavor(self, flavor):
        return self.nova.flavors.delete(flavor)

    def _get_keystoneclient(self, username, password, tenant_name, auth_url,
                            retries=3, ca_cert=None):
        keystone = None
        for i in range(retries):
            try:
                if ca_cert:
                    keystone = KeystoneClient(username=username,
                                              password=password,
                                              tenant_name=tenant_name,
                                              auth_url=auth_url,
                                              cacert=ca_cert)

                else:
                    keystone = KeystoneClient(username=username,
                                              password=password,
                                              tenant_name=tenant_name,
                                              auth_url=auth_url)
                break
            except ClientException as e:
                err = "Try nr {0}. Could not get keystone client, error: {1}"
                LOGGER.warning(err.format(i + 1, e))
                time.sleep(5)
        if not keystone:
            raise
        return keystone
