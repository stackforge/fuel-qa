#    Copyright 2015 Mirantis, Inc.
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

import os
import os.path
import time

from proboscis import test
from proboscis.asserts import assert_true

from fuelweb_test.helpers.decorators import log_snapshot_on_error
from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.common import Common
from fuelweb_test import logger
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import CONTRAIL_PLUGIN_PATH
from fuelweb_test.settings import CONTRAIL_PLUGIN_PACK_UB_PATH
from fuelweb_test.settings import CONTRAIL_PLUGIN_PACK_CEN_PATH
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["plugins"])
class ContrailPlugin(TestBasic):
    """ContrailPlugin."""  # TODO documentation

    master_path = '/var/www/nailgun/plugins/contrail-1.0'
    add_ub_packag = \
        '/var/www/nailgun/plugins/contrail-1.0/' \
        'repositories/ubuntu/contrail-setup*'
    add_cen_packeg = \
        '/var/www/nailgun/plugins/contrail-1.0/' \
        'repositories/centos/Packages/contrail-setup*'

    def upload_packages(self, node_ssh, pack_path, master_path):
        if os.path.splitext(pack_path)[1] in [".deb", ".rpm"]:
            pkg_name = os.path.basename(pack_path)
            logger.debug("Uploading package {0} "
                         "to master node".format(pkg_name))
            node_ssh.upload(pack_path, master_path)
        else:
            logger.error('Failed to upload file')

    def install_packages(self, remote, master_path):
        command = "cd " + master_path + " && ./install.sh"
        logger.info('The command is %s', command)
        remote.execute_async(command)
        time.sleep(50)
        os.path.isfile(self.add_ub_packag or self.add_cen_packeg)

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["install_contrail"])
    @log_snapshot_on_error
    def install_contrail(self):
        """Install Contrail Plugin and create cluster

        Scenario:
            1. Revert snapshot "ready_with_5_slaves"
            2. Upload contrail plugin to the master node
            3. Install plugin and additional packages
            4. Enable Neutron with VLAN segmentation
            5. Create cluster

        Duration 20 min

        """
        self.env.revert_snapshot("ready_with_5_slaves")

        # copy plugin to the master node
        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PATH, '/var')

        # install plugin
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(CONTRAIL_PLUGIN_PATH))

        # copy additional packages to the master node
        self.upload_packages(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PACK_UB_PATH,
            self.master_path
        )

        self.upload_packages(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PACK_CEN_PATH,
            self.master_path
        )

        # install packages
        self.install_packages(self.env.d_env.get_admin_remote(),
                              self.master_path)

        # create cluster
        segment_type = 'vlan'
        self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": segment_type,
            }
        )

        self.env.make_snapshot("install_contrail")

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_contrail"])
    @log_snapshot_on_error
    def deploy_contrail(self):
        """Deploy a cluster with Contrail Plugin

        Scenario:
            1. Revert snapshot "ready_with_5_slaves"
            2. Upload plugin to the master node
            3. Install plugin and additional packages
            4. Enable Neutron with VLAN segmentation
            5. Create cluster
            6. Add 3 nodes with Operating system role
            and 1 node with controller role
            7. Enable Contrail plugin
            8. Deploy cluster with plugin

        Duration 90 min

        """
        self.env.revert_snapshot("ready_with_5_slaves")

        # copy plugin to the master node

        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PATH, '/var')

        # install plugin
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(CONTRAIL_PLUGIN_PATH))

        # copy additional packages to the master node
        self.upload_packages(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PACK_UB_PATH,
            self.master_path
        )

        self.upload_packages(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PACK_CEN_PATH,
            self.master_path
        )

        # install packages
        self.install_packages(self.env.d_env.get_admin_remote(),
                              self.master_path)

        # create cluster
        segment_type = 'vlan'
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": segment_type,
            }
        )

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['base-os'],
                'slave-02': ['base-os'],
                'slave-03': ['base-os'],
                'slave-04': ['controller']
            },
            contrail=True
        )

        plugin_name = 'contrail'
        msg = "Plugin couldn't be enabled. Check plugin version. Test aborted"
        assert_true(
            self.fuel_web.check_plugin_exists(cluster_id, plugin_name),
            msg)
        logger.debug('we have contrail element')
        options = {'metadata/enabled': True,
                   'contrail_public_if/value': 'eth1'}
        self.fuel_web.update_plugin_data(cluster_id, plugin_name, options)

        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.env.make_snapshot("deploy_contrail")

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_controller_compute_contrail"])
    def deploy_controller_compute_contrail(self):
        """Deploy cluster with 1 controller, 1 compute,
        3 base-os and install contrail plugin

        Scenario:
            1. Revert snapshot "ready_with_5_slaves"
            2. Upload plugin to the master node
            3. Install plugin and additional packages
            4. Enable Neutron with VLAN segmentation
            5. Create cluster
            6. Add 3 nodes with Operating system role,
            1 node with controller role and 1 node with compute role
            7. Enable Contrail plugin
            8. Deploy cluster with plugin
            9. Create net and subnet
            10. Run OSTF tests

        Duration 110 min

        """
        self.env.revert_snapshot("ready_with_5_slaves")

        # copy plugin to the master node

        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PATH, '/var')

        # install plugin
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(CONTRAIL_PLUGIN_PATH))

        # copy additional packages to the master node
        self.upload_packages(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PACK_UB_PATH,
            self.master_path
        )

        self.upload_packages(
            self.env.d_env.get_admin_remote(),
            CONTRAIL_PLUGIN_PACK_CEN_PATH,
            self.master_path
        )

        # install packages
        self.install_packages(self.env.d_env.get_admin_remote(),
                              self.master_path)

        # create cluster
        segment_type = 'vlan'
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": segment_type,
            }
        )

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['base-os'],
                'slave-02': ['base-os'],
                'slave-03': ['base-os'],
                'slave-04': ['controller'],
                'slave-05': ['compute', 'cinder']
            },
            contrail=True
        )

        # fill public field in contrail settings
        plugin_name = 'contrail'
        msg = "Plugin couldn't be enabled. Check plugin version. Test aborted"
        assert_true(
            self.fuel_web.check_plugin_exists(cluster_id, plugin_name),
            msg)
        logger.debug('we have contrail element')
        options = {'metadata/enabled': True,
                   'contrail_public_if/value': 'eth1'}
        self.fuel_web.update_plugin_data(cluster_id, plugin_name, options)

        # deploy cluster
        self.fuel_web.deploy_cluster_wait(cluster_id)

        # create net and subnet
        contr_ip = self.fuel_web.get_public_vip(cluster_id)
        logger.info('The ip is %s', contr_ip)
        net = Common(
            controller_ip=contr_ip, user='admin',
            password='admin', tenant='admin'
        )

        net.neutron.create_network(body={
            'network': {
                'name': 'net04',
                'admin_state_up': True
            }
        })

        network_id = ''
        network_dic = net.neutron.list_networks()
        for dd in network_dic['networks']:
            if dd.get("name") == "net04":
                network_id = dd.get("id")

        if network_id == "":
            logger.error('Network id empty')

        logger.debug("id {0} to master node".format(network_id))

        net.neutron.create_subnet(body={
            'subnet': {
                'network_id': network_id,
                'ip_version': 4,
                'cidr': '10.100.0.0/24',
                'name': 'subnetname04'
            }
        })

        # Tests using north-south connectivity are expected to fail because
        # they require additional gateway nodes, and specific contrail
        # settings. This mark is a workaround until it's verified
        # and tested manually.
        # When it will be done 'should_fail=2' and
        # 'failed_test_name' parameter should be removed.

        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            should_fail=2,
            failed_test_name=[
                ('Check network connectivity from instance via floating IP',
                 'Launch instance with file injection')
            ]
        )

    @test(depends_on=[SetupEnvironment.prepare_slaves_9],
          groups=["deploy_ha_contrail_plugin"])
    @log_snapshot_on_error
    def deploy_ha_contrail_plugin(self):
        """Deploy HA Environment with Contrail Plugin

        Scenario:
            1. Revert snapshot "ready_with_9_slaves"
            2. Upload plugin to the master node
            3. Install plugin and additional packages
            4. Enable Neutron with VLAN segmentation
            5. Create cluster
            6. Add 3 nodes with Operating system role and
            1 node with controller role
            7. Enable Contrail plugin
            8. Deploy cluster with plugin
            9. Add 1 node with compute role
            10. Deploy cluster
            11. Run OSTF tests
            12. Add 2 nodes with controller role and
            1 node with compute + cinder role
            13. Deploy cluster
            14. Run OSTF tests

        Duration 140 min

        """

        self.env.revert_snapshot("ready_with_9_slaves")

        # copy plugin to the master node
        checkers.upload_tarball(self.env.d_env.get_admin_remote(),
                                CONTRAIL_PLUGIN_PATH, '/var')

        # install plugin
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(CONTRAIL_PLUGIN_PATH))

        # copy additional packages to the master node
        self.upload_contrail_packages()

        # install packages
        self.install_packages(self.env.d_env.get_admin_remote(),
                              self.master_path)

        # create cluster: 3 nodes with Operating system role
        # and 1 node with controller role
        segment_type = 'vlan'
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": segment_type,
            }
        )

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['base-os'],
                'slave-02': ['base-os'],
                'slave-03': ['base-os'],
                'slave-04': ['controller'],
            },
            contrail=True
        )

        attr = self.fuel_web.client.get_cluster_attributes(cluster_id)
        if 'contrail' in attr['editable']:
            logger.debug('we have contrail element')
            plugin_data = attr['editable']['contrail']['metadata']
            plugin_data['enabled'] = True
            public_int = attr['editable']['contrail']['contrail_public_if']
            public_int['value'] = 'eth1'

        self.fuel_web.client.update_cluster_attributes(cluster_id, attr)

        self.fuel_web.deploy_cluster_wait(cluster_id)

        # create net and subnet
        contr_ip = self.fuel_web.get_public_vip(cluster_id)
        logger.info('The ip is %s', contr_ip)
        net = Common(
            controller_ip=contr_ip, user='admin',
            password='admin', tenant='admin'
        )

        net.neutron.create_network(body={
            'network': {
                'name': 'net04',
                'admin_state_up': True
            }
        })

        network_id = ''
        network_dic = net.neutron.list_networks()
        for dd in network_dic['networks']:
            if dd.get("name") == "net04":
                network_id = dd.get("id")

        if network_id == "":
            logger.error('Network id empty')

        logger.debug("id {0} to master node".format(network_id))

        net.neutron.create_subnet(body={
            'subnet': {
                'network_id': network_id,
                'ip_version': 4,
                'cidr': '10.100.0.0/24',
                'name': 'subnet04'
            }
        })

        # add one node with compute role
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-05': ['compute'],
            }
        )

        self.fuel_web.deploy_cluster_wait(cluster_id)

        # Tests using north-south connectivity are expected to fail because
        # they require additional gateway nodes, and specific contrail
        # settings. This mark is a workaround until it's verified
        # and tested manually.
        # When it will be done 'should_fail=2' and
        # 'failed_test_name' parameter should be removed.
        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            should_fail=2,
            failed_test_name=[('Check network connectivity '
                               'from instance via floating IP'),
                              ('Launch instance with file injection')]
        )

        # add to cluster 2 nodes with controller role and one
        # with compute, cinder role and deploy cluster
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-06': ['controller'],
                'slave-07': ['controller'],
                'slave-08': ['compute', 'cinder']
            }
        )

        self.fuel_web.deploy_cluster_wait(cluster_id)

        # Tests using north-south connectivity are expected to fail because
        # they require additional gateway nodes, and specific contrail
        # settings. This mark is a workaround until it's verified
        # and tested manually.
        # When it will be done 'should_fail=2' and
        # 'failed_test_name' parameter should be removed.
        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            should_fail=2,
            failed_test_name=[('Check network connectivity'
                               ' from instance via floating IP'),
                              ('Launch instance with file injection')]
        )
