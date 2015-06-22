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
from proboscis import test

from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test import logger
from fuelweb_test import settings
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["reduced_footprint"])
class ReducedFootprint(TestBasic):
    """ReducedFootprint."""  # TODO documentation

    @test(depends_on=[SetupEnvironment.prepare_slaves_1],
          groups=["smallest_environment"])
    @log_snapshot_after_test
    def smallest_environment(self):
        """Deploy on smallest environment

        Scenario:
            1. Create cluster
            2. Assign virt role to physical node
            3. Upload 3 VMs configuration
            4. Assign controller roles to VMs and deploy them
            5. Run OSTF tests
            6. Run Network check

        Duration 310m
        """
        self.env.revert_snapshot("ready_with_1_slaves")
        data = {
            'net_provider': 'neutron',
            'net_segment_type': 'gre'
            }

        data_vm_1 = '{"id": 1}'
        data_vm_2 = {
            "id": 2,
            "mem": 2,
            "cpu": 1
            }
        data_vm_3 = {
            "id": 3,
            "mem": 3,
            "cpu": 2
            }
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=settings.DEPLOYMENT_MODE_HA,
            settings=data)

        # Turn on advanced mode
        remote = self.env.d_env.get_admin_remote()
        checkers.check_enable_advanced_mode(remote, '/etc/fuel/version.yaml')
        checkers.restart_nailgun(remote)

        self.fuel_web.update_nodes(
            cluster_id,
            {'slave-01': ['compute', 'virt']})

        # Upload 3 VMs configuration
        logger.info('Upload 3 VMs configuration')
        self.fuel_web.create_vms_nodes(data_vm_1)

        # Spawn VM
        logger.info('Spawn VMs')
        self.fuel_web.run_spawn_vms(cluster_id, timeout=90 * 60, interval=5)

        # Assign controller
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['compute', 'virt'],
                'slave-02': ['controller'],
                'slave-03': ['controller'],
                'slave-04': ['controller']
            }
        )

        # Cluster deploy
        self.fuel_web.deploy_cluster_wait(cluster_id)

        # Check network
        self.fuel_web.verify_network(cluster_id)

        # Run ostf
        self.fuel_web.run_ostf(cluster_id, test_sets=['ha', 'smoke', 'sanity'])

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["big_reduced_footprint"])
    @log_snapshot_after_test
    def big_reduced_footprint(self):
        """Deploy with three hardware computes and controllers across them

        Scenario:
            1. Create cluster
            2. Add 3 node with compute roles
            3. Create three VMs, by one for each compute
            4. Add controller role and deploy them
            5. Run OSTF tests
            6. Run Network check

        Duration 100m
        """
        self.env.revert_snapshot("ready_with_3_slaves")

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=settings.DEPLOYMENT_MODE_HA)

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['compute', 'virt'],
                'slave-02': ['compute', 'virt'],
                'slave-03': ['compute', 'virt'],
            }
        )

        # Cluster deploy
        self.fuel_web.deploy_cluster_wait(cluster_id)

        # Check network
        self.fuel_web.verify_network(cluster_id)

        # Run ostf
        self.fuel_web.run_ostf(cluster_id, test_sets=['ha', 'smoke', 'sanity'])

        # Add controller role to VM?
        self.env.bootstrap_nodes(self.env.d_env.nodes().slaves[2:6])

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["mixed_environment"])
    @log_snapshot_after_test
    def mixed_environment(self):
        """Deploy mixed HW and Virtual environment

        Scenario:

            1. Add virt role
            2. Add two new HW nodes
            3. Add one VM
            4. Add controller roles and deploy them
            5. Run OSTF tests
            6. Run Network check

        Duration 155m
        """
        self.env.revert_snapshot("ready_with_3_slaves")

        cluster_id = self.fuel_web.get_last_created_cluster()

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-03': ['controller'],
                'slave-04': ['controller'],
                'slave-05': ['controller'],
            }
        )

        # Cluster deploy
        self.fuel_web.deploy_cluster_wait(cluster_id)

        # Check network
        self.fuel_web.verify_network(cluster_id)

        # Run ostf
        self.fuel_web.run_ostf(cluster_id, test_sets=['ha', 'smoke', 'sanity'])
