#    Copyright 2016 Mirantis, Inc.
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
from proboscis.asserts import assert_true
from proboscis.asserts import assert_equal
from proboscis.asserts import assert_not_equal

from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.helpers.utils import install_configdb
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


class TestsConfigDB(TestBasic):
    """Tests ConfigDB"""  # TODO documentations

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["install_configdb_extension", 'base_tests_configdb'])
    @log_snapshot_after_test
    def install_configdb_extension(self):
        """ Install and check ConfigDB

        Scenario:
            1. Revert snapshot with 5 slaves booted
            2. Install configDB extension
            3. Verify main actions

        Duration: # TODO

        Snapshot: ready_with_configdb
        """

        self.env.revert_snapshot('ready_with_5_slaves')
        install_configdb(master_node_ip=self.ssh_manager.admin_ip)

        # get_data
        components = self.fuel_web.client.get_components()
        envs = self.fuel_web.client.get_envirionments()

        assert_true(not components)
        assert_true(not envs)

        # post data
        component = {
            "name": "comp1",
            "resource_definitions": [
                {"name": "resource1", "content": {}},
                {"name": "slashed/resource", " content": {}}
            ]
        }

        env = {
            "name": "env1",
            "components": ["comp1"],
            "hierarchy_levels": ["nodes"]
        }
        # Create component
        self.fuel_web.client.post_components(component)
        # Create env with component
        self.fuel_web.client.post_envirionments(env)

        #Get env resource
        global_res = self.fuel_web.client.get_global_resource_value(1, 1)
        #Get node resource value
        node_res = self.fuel_web.client.get_node_resource_value(1, 1, 1)

        assert_true(not global_res)
        assert_true(not node_res)

        node_value = {'node_key': 'node_value'}
        global_value = {'global_key': 'global_value'}

        #Put data in
        self.fuel_web.client.put_node_resource_value(1, 1, 1, node_value)
        self.fuel_web.client.put_global_resource_value(1, 1, global_value)

        assert_equal(
            self.fuel_web.client.get_global_resource_value(1, 1),
            self.fuel_web.client.get_global_resource_value(1, 1,
                                                           effective=True)
        )

        node_uploaded = self.fuel_web.client.get_node_resource_value(1, 1, 1)
        node_effective = self.fuel_web.client.get_node_resource_value(
                1, 1, 1, effective=True)
        assert_not_equal(node_uploaded, node_effective)
        merged_value = node_value.copy()
        merged_value.update(global_value)
        assert_equal(merged_value, node_effective)

        #Override global
        global_override = {'global_key': 'global_override'}
        merged_value.update(global_override)

        self.fuel_web.client.put_global_resource_override(1, 1,
                                                          global_override)

        node_effective = self.fuel_web.client.get_node_resource_value(
                1, 1, 1, effective=True)
        assert_equal(node_effective, merged_value)

        # Try to update data
        global_new = {'global_key': 'global_new'}

        self.fuel_web.client.put_global_resource_value(1, 1, global_new)

        node_effective = self.fuel_web.client.get_node_resource_value(
                1, 1, 1, effective=True)
        assert_equal(node_effective, merged_value)

        # Override node level
        # Check Node level override takes priority over global override
        node_override = {'global_key': 'node_override'}
        self.fuel_web.client.put_node_resource_overrides(1, 1, 1,
                                                         node_override)

        node_effective = self.fuel_web.client.get_node_resource_value(
                1, 1, 1, effective=True)
        merged_value.update(node_override)
        assert_equal(node_effective, merged_value)

        node_effective = self.fuel_web.client.get_node_resource_value(
                1, 1, 2, effective=True)

        assert_equal(node_effective, global_override)
