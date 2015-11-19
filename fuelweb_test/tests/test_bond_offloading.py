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

from copy import deepcopy

from proboscis.asserts import assert_equal
from proboscis import test

from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.test_bonding_base import BondingTest


@test(groups=["bonding_ha_one_controller", "bonding", "offloading"])
class TestOffloading(BondingTest):

    offloading_types = ['generic-receive-offload',
                        'generic-segmentation-offload',
                        'tcp-segmentation-offload']

    def update_offloads(self, node_id, update_values, interface_to_update):
        interfaces = self.fuel_web.client.get_node_interfaces(node_id)

        for i in interfaces:
            if i['name'] == interface_to_update:
                for new_mode in update_values['offloading_modes']:
                    is_mode_exist = False
                    for mode in i['offloading_modes']:
                        if mode['name'] == new_mode['name']:
                            is_mode_exist = True
                            mode.update(new_mode)
                            break
                    if not is_mode_exist:
                        i['offloading_modes'].append(new_mode)
        self.fuel_web.client.put_node_interfaces(
            [{'id': node_id, 'interfaces': interfaces}])

    def check_offload(self, node, eth, offload_type):
        command = "ethtool --show-offload %s | awk '/%s/ {print $2}'"
        offload_status = node.execute(command % (eth, offload_type))
        assert_equal(offload_status['exit_code'], 0,
                     "Failed to get Offload {0} "
                     "on node {1}".format(offload_type, node))
        return ''.join(node.execute(
            command % (eth, offload_type))['stdout']).rstrip()

    def get_bond_slaves(self, bond_config, bond_name):
        bond_slaves = []
        for bond in [bond for bond in bond_config]:
            if bond['name'] == bond_name:
                for slave in bond['slaves']:
                    bond_slaves.append(slave['name'])
        return bond_slaves

    def prepare_offloading_modes(self, interfaces, state):
        offloading_modes = []
        for name in self.offloading_types:
            offloading_modes.append({'name': name, 'state': state, 'sub': []})

        offloadings = []
        for interface in interfaces:
            templ = {'name': interface,
                     'offloading_modes': deepcopy(offloading_modes)}
            offloadings.append(templ)
        return offloadings

    def check_offloading_modes(self, nodes, interfaces, offloading_types,
                               state):
        for node in nodes:
            for eth in interfaces:
                for name in self.offloading_types:
                    with self.env.d_env.get_ssh_to_remote(node['ip']) as host:
                        result = self.check_offload(host, eth, name)
                        assert_equal(
                            result, 'on' if state == 'true' else 'off',
                            "Offload type '{0}': '{1}' - node-{2}, {3}".format(
                                name, result, node['id'], eth))

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["offloading_off_1_bond_neutron_vlan", "bonding",
                  "offloading"])
    @log_snapshot_after_test
    def offloading_off_1_bond_neutron_vlan(self):
        """Deploy cluster with new offload modes and neutron VLAN

        Scenario:
            1. Create cluster with neutron VLAN
            2. Add 1 node with controller role
            3. Add 1 node with compute role and 1 node with cinder role
            4. Setup single bonded interface for all nodes using network yaml
            5. Set off offloading types for the single bonded interface
            6. Run network verification
            7. Deploy the cluster
            8. Run network verification
            9. Run OSTF
            10. Verify offloading types for the bonded interfaces

        Duration 60m
        Snapshot offloading_off_1_bond_neutron_vlan

        """
        self.env.revert_snapshot("ready_with_3_slaves")

        self.show_step(1)
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": 'vlan',
            }
        )

        bond = 'bond0'
        state = 'false'
        interfaces = self.get_bond_slaves(self.BOND_CONFIG, bond)
        interfaces.append(bond)
        offloading_modes = self.prepare_offloading_modes(interfaces, state)

        self.show_step(2)
        self.fuel_web.update_nodes(
            cluster_id, {
                'slave-01': ['controller'],
                'slave-02': ['compute'],
                'slave-03': ['cinder']
            }
        )

        self.show_step(3)
        nodes = self.fuel_web.client.list_cluster_nodes(cluster_id)
        self.show_step(4)
        self.show_step(5)
        for node in nodes:
            self.fuel_web.update_node_networks(
                node['id'],
                interfaces_dict=deepcopy(self.INTERFACES),
                raw_data=deepcopy(self.BOND_CONFIG))
            for offloading in offloading_modes:
                self.update_offloads(
                    node['id'], deepcopy(offloading), offloading['name'])

        self.show_step(6)
        self.fuel_web.verify_network(cluster_id)
        self.show_step(7)
        self.fuel_web.deploy_cluster_wait(cluster_id, check_services=False)

        self.show_step(8)
        self.fuel_web.verify_network(cluster_id)

        self.show_step(9)
        self.fuel_web.run_ostf(cluster_id=cluster_id)

        self.show_step(10)
        self.check_offloading_modes(nodes, interfaces,
                                    self.offloading_types, state)

        self.env.make_snapshot("offloading_off_1_bond_neutron_vlan")

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["offloading_on_1_bond_neutron_vlan", "bonding",
                  "offloading"])
    @log_snapshot_after_test
    def offloading_on_1_bond_neutron_vlan(self):
        """Deploy cluster with new offload modes and neutron VLAN

        Scenario:
            1. Create cluster with neutron VLAN
            2. Add 1 node with controller role
            3. Add 1 node with compute role and 1 node with cinder role
            4. Setup single bonded interface for all nodes using network yaml
            5. Set on offloading types for the single bonded interface
            6. Run network verification
            7. Deploy the cluster
            8. Run network verification
            9. Run OSTF
            10. Verify offloading types for the bonded interfaces

        Duration 60m
        Snapshot offloading_on_1_bond_neutron_vlan

        """
        self.env.revert_snapshot("ready_with_3_slaves")

        self.show_step(1)
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": 'vlan',
            }
        )

        bond = 'bond0'
        state = 'true'
        interfaces = self.get_bond_slaves(self.BOND_CONFIG, bond)
        interfaces.append(bond)
        offloading_modes = self.prepare_offloading_modes(interfaces, state)

        self.show_step(2)
        self.fuel_web.update_nodes(
            cluster_id, {
                'slave-01': ['controller'],
                'slave-02': ['compute'],
                'slave-03': ['cinder']
            }
        )

        self.show_step(3)
        nodes = self.fuel_web.client.list_cluster_nodes(cluster_id)
        self.show_step(4)
        self.show_step(5)
        for node in nodes:
            self.fuel_web.update_node_networks(
                node['id'],
                interfaces_dict=deepcopy(self.INTERFACES),
                raw_data=deepcopy(self.BOND_CONFIG))
            for offloading in offloading_modes:
                self.update_offloads(
                    node['id'], deepcopy(offloading), offloading['name'])

        self.show_step(6)
        self.fuel_web.verify_network(cluster_id)
        self.show_step(7)
        self.fuel_web.deploy_cluster_wait(cluster_id, check_services=False)

        self.show_step(8)
        self.fuel_web.verify_network(cluster_id)

        self.show_step(9)
        self.fuel_web.run_ostf(cluster_id=cluster_id)

        self.show_step(10)
        self.check_offloading_modes(nodes, interfaces,
                                    self.offloading_types, state)

        self.env.make_snapshot("offloading_on_1_bond_neutron_vlan")

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["offloading_off_1_bond_neutron_vxlan", "bonding",
                  "offloading"])
    @log_snapshot_after_test
    def offloading_off_1_bond_neutron_vxlan(self):
        """Deploy cluster with new offload modes and neutron VXLAN

        Scenario:
            1. Create cluster with neutron VXLAN
            2. Add 1 node with controller role
            3. Add 1 node with compute role and 1 node with cinder role
            4. Setup single bonded interface for all nodes using network yaml
            5. Set off offloading types for the single bonded interface
            6. Run network verification
            7. Deploy the cluster
            8. Run network verification
            9. Run OSTF
            10. Verify offloading types for the bonded interfaces

        Duration 60m
        Snapshot offloading_off_1_bond_neutron_vxlan

        """
        self.env.revert_snapshot("ready_with_3_slaves")

        self.show_step(1)
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": 'gre',
            }
        )

        bond = 'bond0'
        state = 'false'
        interfaces = self.get_bond_slaves(self.BOND_CONFIG, bond)
        interfaces.append(bond)
        offloading_modes = self.prepare_offloading_modes(interfaces, state)

        self.show_step(2)
        self.fuel_web.update_nodes(
            cluster_id, {
                'slave-01': ['controller'],
                'slave-02': ['compute'],
                'slave-03': ['cinder']
            }
        )

        self.show_step(3)
        nodes = self.fuel_web.client.list_cluster_nodes(cluster_id)
        self.show_step(4)
        self.show_step(5)
        for node in nodes:
            self.fuel_web.update_node_networks(
                node['id'],
                interfaces_dict=deepcopy(self.INTERFACES),
                raw_data=deepcopy(self.BOND_CONFIG))
            for offloading in offloading_modes:
                self.update_offloads(
                    node['id'], deepcopy(offloading), offloading['name'])

        self.show_step(6)
        self.fuel_web.verify_network(cluster_id)
        self.show_step(7)
        self.fuel_web.deploy_cluster_wait(cluster_id, check_services=False)

        self.show_step(8)
        self.fuel_web.verify_network(cluster_id)

        self.show_step(9)
        self.fuel_web.run_ostf(cluster_id=cluster_id)

        self.show_step(10)
        self.check_offloading_modes(nodes, interfaces,
                                    self.offloading_types, state)

        self.env.make_snapshot("offloading_off_1_bond_neutron_vlan")

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["offloading_on_1_bond_neutron_vxlan", "bonding",
                  "offloading"])
    @log_snapshot_after_test
    def offloading_on_1_bond_neutron_vxlan(self):
        """Deploy cluster with new offload modes and neutron VXLAN

        Scenario:
            1. Create cluster with neutron VXLAN
            2. Add 1 node with controller role
            3. Add 1 node with compute role and 1 node with cinder role
            4. Setup single bonded interface for all nodes using network yaml
            5. Set on offloading types for the single bonded interface
            6. Run network verification
            7. Deploy the cluster
            8. Run network verification
            9. Run OSTF
            10. Verify offloading types for the bonded interfaces

        Duration 60m
        Snapshot offloading_on_1_bond_neutron_vxlan

        """
        self.env.revert_snapshot("ready_with_3_slaves")

        self.show_step(1)
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": 'gre',
            }
        )

        bond = 'bond0'
        state = 'true'
        interfaces = self.get_bond_slaves(self.BOND_CONFIG, bond)
        interfaces.append(bond)
        offloading_modes = self.prepare_offloading_modes(interfaces, state)

        self.show_step(2)
        self.fuel_web.update_nodes(
            cluster_id, {
                'slave-01': ['controller'],
                'slave-02': ['compute'],
                'slave-03': ['cinder']
            }
        )

        self.show_step(3)
        nodes = self.fuel_web.client.list_cluster_nodes(cluster_id)
        self.show_step(4)
        self.show_step(5)
        for node in nodes:
            self.fuel_web.update_node_networks(
                node['id'],
                interfaces_dict=deepcopy(self.INTERFACES),
                raw_data=deepcopy(self.BOND_CONFIG))
            for offloading in offloading_modes:
                self.update_offloads(
                    node['id'], deepcopy(offloading), offloading['name'])

        self.show_step(6)
        self.fuel_web.verify_network(cluster_id)
        self.show_step(7)
        self.fuel_web.deploy_cluster_wait(cluster_id, check_services=False)

        self.show_step(8)
        self.fuel_web.verify_network(cluster_id)

        self.show_step(9)
        self.fuel_web.run_ostf(cluster_id=cluster_id)

        self.show_step(10)
        self.check_offloading_modes(nodes, interfaces,
                                    self.offloading_types, state)

        self.env.make_snapshot("offloading_on_1_bond_neutron_vxlan")
