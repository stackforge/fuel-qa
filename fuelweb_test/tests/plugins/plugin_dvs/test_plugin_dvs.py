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
import os
import time

from proboscis import test
from proboscis.asserts import assert_true
from fuelweb_test.helpers import checkers

from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test import logger
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import VCENTER_IP
from fuelweb_test.settings import VCENTER_USERNAME
from fuelweb_test.settings import VCENTER_PASSWORD
from fuelweb_test.settings import VCENTER_DATACENTER
from fuelweb_test.settings import VCENTER_DATASTORE
from fuelweb_test.settings import DVS_PLUGIN_PATH
from fuelweb_test.settings import NEUTRON_SEGMENT_TYPE
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["plugins"])
class TestDVSPlugin(TestBasic):

    # constants
    plugin_name = 'fuel-plugin-vmware-dvs'
    msg = "Plugin couldn't be enabled. Check plugin version. Test aborted"

    def install_dvs_plugin(self):
        # copy plugins to the master node
        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            DVS_PLUGIN_PATH, "/var")

        # install plugin
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(DVS_PLUGIN_PATH))

    def enable_plugin(self, cluster_id=None):
        assert_true(
            self.fuel_web.check_plugin_exists(cluster_id, self.plugin_name),
            self.msg)
        options = {'metadata/enabled': True}
        self.fuel_web.update_plugin_data(cluster_id, self.plugin_name, options)

        logger.info("cluster is {}".format(cluster_id))

    def run_smoke(self, cluster_id=None):
        try:
            self.fuel_web.run_ostf(cluster_id, test_sets=['smoke'],
                                   timeout=60 * 60)
        except AssertionError:
            time_to_wait = 660
            logger.debug("Tests failed from first probe,"
                         " waite {} seconds try one more time"
                         " and if it fails again - "
                         "tests will fail ".format(time_to_wait))
            time.sleep(time_to_wait)
            self.fuel_web.run_ostf(cluster_id,
                                   test_sets=['smoke'],
                                   timeout=60 * 60)

    def add_dhcp_lease(self, remote=None):
        path = '/etc/puppet/modules/nova/manifests/network.pp'
        d = "  nova_config { 'DEFAULT/dhcp_lease_time': value=> '600'}\n"
        old_file = remote.open(path, 'r')
        contents = old_file.readlines()
        contents.insert((contents.index('  if $floating_range {\n') - 1), d)
        new_file = remote.open(path, 'w')
        contents = "".join(contents)
        new_file.write(contents)
        new_file.close()

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["dvs_vcenter_smoke"])
    @log_snapshot_after_test
    def dvs_vcenter_smoke(self):
        """Deploy cluster with plugin and vmware datastore backend

        Scenario:
            1. Create cluster
            2. Add 1 node with controller role
            3. Add 1 node with cinder-vmdk role
            3. Deploy the cluster
            4. Run OSTF

        """
        self.env.revert_snapshot("ready_with_3_slaves")

        self.add_dhcp_lease(remote=self.env.d_env.get_admin_remote())

        self.install_dvs_plugin()

        # Configure cluster
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "images_vcenter": True,
                "net_provider": 'neutron',
                "net_segment_type": NEUTRON_SEGMENT_TYPE,
            },
            vcenter_value={
                "glance": {
                    "vcenter_username": VCENTER_USERNAME,
                    "datacenter": VCENTER_DATACENTER,
                    "vcenter_host": VCENTER_IP,
                    "vcenter_password": VCENTER_PASSWORD,
                    "datastore": VCENTER_DATASTORE},
                "availability_zones": [
                    {"vcenter_username": VCENTER_USERNAME,
                     "nova_computes": [
                         {"datastore_regex": ".*",
                          "vsphere_cluster": "Cluster1",
                          "service_name": "vmcluster"
                          },
                         {"datastore_regex": ".*",
                          "vsphere_cluster": "Cluster2",
                          "service_name": "vmcluster2"
                          },
                     ],
                     "vcenter_host": VCENTER_IP,
                     "az_name": "vcenter",
                     "vcenter_password": VCENTER_PASSWORD,
                     }]
            }
        )

        self.enable_plugin(cluster_id=cluster_id)

        # Assign role to node
        self.fuel_web.update_nodes(
            cluster_id,
            {'slave-01': ['controller'],
             'slave-02': ['cinder-vmware'], }
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id, test_sets=['sanity'])

        self.run_smoke(cluster_id=cluster_id)

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["dvs_vcenter_ha_mode"])
    @log_snapshot_after_test
    def dvs_vcenter_ha_mode(self):
        """Deploy cluster with plugin and vmware datastore backend

        Scenario:
            1. Create cluster
            2. Add 3 node with controller role
            3. Add 1 node with cinder-vmdk role
            4. Add 1 node with compute role
            5. Deploy the cluster
            6. Run OSTF

        """
        self.env.revert_snapshot("ready_with_5_slaves")

        self.add_dhcp_lease(remote=self.env.d_env.get_admin_remote())

        self.install_dvs_plugin()

        # Configure cluster
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": NEUTRON_SEGMENT_TYPE,
            },
            vcenter_value={
                "glance": {
                    "vcenter_username": "",
                    "datacenter": "",
                    "vcenter_host": "",
                    "vcenter_password": "",
                    "datastore": "", },
                "availability_zones": [
                    {"vcenter_username": VCENTER_USERNAME,
                     "nova_computes": [
                         {"datastore_regex": ".*",
                          "vsphere_cluster": "Cluster1",
                          "service_name": "vmcluster"
                          },
                         {"datastore_regex": ".*",
                          "vsphere_cluster": "Cluster2",
                          "service_name": "vmcluster2"
                          },
                     ],
                     "vcenter_host": VCENTER_IP,
                     "az_name": "vcenter",
                     "vcenter_password": VCENTER_PASSWORD,
                     }]
            }
        )

        self.enable_plugin(cluster_id=cluster_id)

        # Assign role to node
        self.fuel_web.update_nodes(
            cluster_id,
            {'slave-01': ['controller'],
             'slave-02': ['controller'],
             'slave-03': ['controller'],
             'slave-04': ['compute'],
             'slave-05': ['cinder-vmware']}
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id, test_sets=['sanity', 'ha'])

        self.run_smoke(cluster_id=cluster_id)

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["dvs_vcenter_ceph"])
    @log_snapshot_after_test
    def dvs_vcenter_ceph(self):
        """Deploy cluster with plugin and vmware datastore backend

        Scenario:
            1. Create cluster
            2. Add 3 node with controller role
            3. Add 1 node with cinder-vmdk role
            4. Add 1 node with compute role
            5. Deploy the cluster
            6. Run OSTF

        """
        self.env.revert_snapshot("ready_with_5_slaves")

        self.add_dhcp_lease(remote=self.env.d_env.get_admin_remote())

        self.install_dvs_plugin()

        # Configure cluster
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                'images_ceph': True,
                'volumes_ceph': True,
                'volumes_lvm': False,
                "net_provider": 'neutron',
                "net_segment_type": NEUTRON_SEGMENT_TYPE,
            },
            vcenter_value={
                "glance": {
                    "vcenter_username": "",
                    "datacenter": "",
                    "vcenter_host": "",
                    "vcenter_password": "",
                    "datastore": "", },
                "availability_zones": [
                    {"vcenter_username": VCENTER_USERNAME,
                     "nova_computes": [
                         {"datastore_regex": ".*",
                          "vsphere_cluster": "Cluster1",
                          "service_name": "vmcluster"
                          },
                         {"datastore_regex": ".*",
                          "vsphere_cluster": "Cluster2",
                          "service_name": "vmcluster2"
                          },
                     ],
                     "vcenter_host": VCENTER_IP,
                     "az_name": "vcenter",
                     "vcenter_password": VCENTER_PASSWORD,
                     }]
            }
        )

        self.enable_plugin(cluster_id=cluster_id)

        # Assign role to node
        self.fuel_web.update_nodes(
            cluster_id,
            {'slave-01': ['controller'],
             'slave-02': ['controller'],
             'slave-03': ['controller'],
             'slave-04': ['cinder', 'ceph-osd'],
             'slave-05': ['cinder-vmware', 'ceph-osd']}
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.fuel_web.run_ostf(
            cluster_id=cluster_id, test_sets=['sanity', 'ha'])

        self.run_smoke(cluster_id=cluster_id)
