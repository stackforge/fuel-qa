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
import ConfigParser
import cStringIO
import os

from proboscis import asserts
from proboscis import test

from fuelweb_test.helpers.decorators import log_snapshot_on_error
from fuelweb_test.helpers import checkers
from fuelweb_test import settings as CONF
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["plugins"])
class GlusterfsPlugin(TestBasic):
    @classmethod
    def check_emc_cinder_config(cls, remote, path):
        command = 'cat {0}'.format(path)
        conf_data = cStringIO.StringIO(remote.execute(command)['output'])
        cinder_conf = ConfigParser.ConfigParser()
        cinder_conf.readfp(conf_data)

        asserts.assert_equal(
            cinder_conf.get('DEFAULT', 'volume_driver'),
            'cinder.volume.drivers.emc.emc_cli_iscsi.EMCCLIISCSIDriver')
        asserts.assert_equal(
            cinder_conf.get('DEFAULT', 'storage_vnx_authentication_type'),
            'global')
        asserts.assert_true(
            cinder_conf.getboolean('DEFAULT',
                                   'destroy_empty_storage_group'))
        asserts.assert_true(
            cinder_conf.getboolean('DEFAULT',
                                   'initiator_auto_registration'))
        asserts.assert_equal(
            cinder_conf.getint('DEFAULT', 'attach_detach_batch_interval'), -1)
        asserts.assert_equal(
            cinder_conf.getint('DEFAULT', 'default_timeout'), 10)
        asserts.assert_equal(
            cinder_conf.get('DEFAULT', 'naviseccli_path'),
            '/opt/Navisphere/bin/naviseccli')

        asserts.assert_true(cinder_conf.has_option('DEFAULT', 'san_ip'))
        asserts.assert_true(cinder_conf.has_option('DEFAULT',
                                                   'san_secondary_ip'))
        asserts.assert_true(cinder_conf.has_option('DEFAULT', 'san_login'))
        asserts.assert_true(cinder_conf.has_option('DEFAULT', 'san_password'))

    @classmethod
    def check_service(cls, remote, service):
        ps_output = remote.execute('ps ax | grep -v grep')['stdout']
        return service in ps_output

    @classmethod
    def check_emc_management_package(cls, remote):
        navicli = checkers.get_package_versions_from_node(remote, 'navicli')
        naviseccli = checkers.\
            get_package_versions_from_node(remote, 'naviseccli')
        return any([out != '' for out in navicli, naviseccli])

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_emc_ha"])
    @log_snapshot_on_error
    def deploy_emc_ha(self):
        """Deploy cluster in ha mode with glusterfs plugin

        Scenario:
            1. Upload plugin to the master node
            2. Install plugin
            3. Create cluster
            4. Add 3 nodes with controller role
            5. Add 2 nodes with compute role
            6. Deploy the cluster
            7. Run network verification
            8. Check plugin installation
            9. Run OSTF

        Duration 35m
        Snapshot deploy_ha_one_controller_glusterfs
        """
        self.env.revert_snapshot("ready_with_5_slaves")

        # copy plugin to the master node

        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            CONF.EMC_PLUGIN_PATH, '/var')

        # install plugin

        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(CONF.EMC_PLUGIN_PATH))

        settings = None

        if CONF.NEUTRON_ENABLE:
            settings = {
                "net_provider": 'neutron',
                "net_segment_type": CONF.NEUTRON_SEGMENT_TYPE
            }

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=CONF.DEPLOYMENT_MODE,
            settings=settings
        )

        attr = self.fuel_web.client.get_cluster_attributes(cluster_id)
        attr = attr["editable"]

        # check plugin installed and attributes have emc options

        for option in ["volumes_emc", "emc_sp_a_ip", "emc_sp_b_ip",
                       "emc_username", "emc_password", "emc_pool_name"]:
            asserts.assert_true(option in attr["editable"]["storage"],
                                "{0} is not in cluster attributes".
                                format(option))

        # enable EMC plugin

        storage_options = attr["editable"]["storage"]
        storage_options["voumes_emc"]["value"] = True
        storage_options["emc_sp_a_ip"]["value"] = CONF.EMC_SP_A_IP
        storage_options["emc_sp_b_ip"]["value"] = CONF.EMC_SP_B_IP
        storage_options["emc_username"]["value"] = CONF.EMC_USERNAME
        storage_options["emc_password"]["value"] = CONF.EMC_PASSWORD
        storage_options["emc_pool_name"]["value"] = CONF.EMC_POOL_NAME

        self.fuel_web.client.update_cluster_attributes(cluster_id, attr)

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['controller'],
                'slave-03': ['controller'],
                'slave-04': ['compute'],
                'slave-05': ['compute'],
            }
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)

        # get remotes for all nodes

        controller_ips = [self.fuel_web.get_nailgun_node_by_name(node)
                          for node in ['slave-01', 'slave-02', 'slave-03']]
        compute_ips = [self.fuel_web.get_nailgun_node_by_name(node)
                       for node in ['slave-04', 'slave-05']]
        controller_remotes = [self.env.d_env.get_ssh_to_remote(ip)
                              for ip in controller_ips]
        compute_remotes = [self.env.d_env.get_ssh_to_remote(ip)
                           for ip in compute_ips]

        # check cinder-volume settings

        for remote in controller_remotes:
            self.check_emc_cinder_config(
                remote=remote, path='/etc/cinder/cinder.conf')
            self.check_emc_management_package(remote=remote)

        # check cinder-volume layout

        cinder_volume_ctrls = [self.check_service(controller, "cinder-volume")
                               for controller in controller_remotes]
        asserts.assert_equal(sum(cinder_volume_ctrls), 1,
                             "Cluster has more than one "
                             "cinder-volume on controllers")
        cinder_volume_comps = [self.check_service(compute, "cinder-volume")
                               for compute in compute_remotes]
        asserts.assert_equal(sum(cinder_volume_comps), 0,
                             "Cluster has active cinder-volume on compute")

        self.fuel_web.verify_network(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            should_fail=2,
            failed_test_name=[''])

        self.env.make_snapshot("deploy_ha_emc")
