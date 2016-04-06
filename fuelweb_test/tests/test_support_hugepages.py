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

from proboscis import asserts
from proboscis import test

from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test import settings
from fuelweb_test import logger
from fuelweb_test.helpers import common
from fuelweb_test.helpers import utils
from fuelweb_test.helpers import os_actions
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["support_hugepages"])
class SupportHugepages(TestBasic):
    """SupportHugepages.

    Required environemnet variables:
        * KVM_USE = True
        * DRIVER_ENABLE_ACPI=true
        * NUMA_NODES=2
        * SLAVE_NODE_CPU=8
        * SLAVE_NODE_MEMORY=4096
        * IFACE_0=ens3
        * IFACE_1=ens4
        * IFACE_2=ens5
        * IFACE_3=ens6
        * IFACE_4=ens7
        * IFACE_5=ens8
    """
    def __init__(self):
        self.os_conn = None
        super(SupportHugepages, self).__init__()

    def boot_instance_validate(self, name, flavor_name, image,
                               expected_host_name, expected_page_size):

        def find_flavor():
            return [
                flavor for flavor in self.os_conn.nova.flavors.list()
                if flavor.name == flavor_name].pop()

        server = self.os_conn.create_server_for_migration(
            flavor=find_flavor().id)

        logger.info(server.get('OS-EXT-SRV-ATTR:host'), expected_host_name)

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["basic_env_for_hugepages"])
    @log_snapshot_after_test
    def basic_env_for_hugepages(self):
        """Basic environment for hugepages

        Scenario:
            1. Create cluster
            2. Add 3 compute nodes and 1 controller node
            3. Check what type of HugePages do support 2M and 1GB
            4. Verify the same HP size is present in CLI
            5. Download attributes for computes and check HP size

        Snapshot: basic_env_for_hugepages

        """
        snapshot_name = 'basic_env_for_hugepages'
        self.check_run(snapshot_name)
        self.env.revert_snapshot("ready_with_5_slaves")

        self.show_step(1)
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=settings.DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": settings.NEUTRON_SEGMENT_TYPE
            }
        )

        self.show_step(2)
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['compute'],
                'slave-02': ['compute'],
                'slave-03': ['compute'],
                'slave-04': ['controller']
            })

        self.show_step(3)
        computes = self.fuel_web.get_nailgun_cluster_nodes_by_roles(
            cluster_id, ['compute'], role_status="pending_roles")
        for compute in computes:
            self.ssh_manager.execute_on_remote(
                ip=compute['ip'],
                cmd="grep \"pse\" /proc/cpuinfo",
                err_msg="HugePages don't support 2M on {}".format(compute))

            self.ssh_manager.execute_on_remote(
                ip=compute['ip'],
                cmd="grep \"pdpe1gb\" /proc/cpuinfo",
                err_msg="HugePages don't support 1GB on {}".format(compute))

        self.show_step(4)
        for compute in computes:
            self.ssh_manager.execute_on_remote(
                ip=self.ssh_manager.admin_ip,
                cmd="fuel2 node show {0} | grep hugepages | "
                    "grep 2048".format(compute['id']),
                err_msg="2M of HugePages isn't present in CLI for "
                        "{0}".format(compute))
            self.ssh_manager.execute_on_remote(
                ip=self.ssh_manager.admin_ip,
                cmd="fuel2 node show {0} | grep hugepages | "
                    "grep 1048576".format(compute['id']),
                err_msg="2M of HugePages isn't present in CLI for "
                        "{0}".format(compute))

        self.show_step(5)
        for compute in computes:
            config = self.fuel_web.client.get_node_attributes(compute['id'])
            asserts.assert_true(
                config['hugepages']['nova']['value']['2048'] == 0,
                "HugePages don't support 2M")
            asserts.assert_true(
                config['hugepages']['nova']['value']['1048576'] == 0,
                "HugePages don't support 1GB")

        self.env.make_snapshot(snapshot_name, is_make=True)

    @test(depends_on=[basic_env_for_hugepages],
          groups=["check_hugepages_distribution_per_numa"])
    @log_snapshot_after_test
    def check_hugepages_distribution_per_numa(self):
        """Basic environment for hugepages

        Scenario:
            1. Create cluster
            2. Add 3 node with compute role
            3. Add 1 nodes with controller role
            4. Check what type of HugePages do support 2M and 1GB
            5. Verify the same HP size is present in CLI
            6. Download attributes for computes and check HP size

        Snapshot: check_hugepages_distribution_per_numa
        """
        # self.env.revert_snapshot("basic_env_for_hugepages")
        cluster_id = self.fuel_web.get_last_created_cluster()
        computes = self.fuel_web.get_nailgun_cluster_nodes_by_roles(
            cluster_id, ['compute'], role_status="pending_roles")
        computes = self.fuel_web.get_nailgun_cluster_nodes_by_roles(
            cluster_id, ['compute'])

        mixed_host = "slave-01"
        one_gb_host = "slave-02"
        two_mb_host = "slave-03"
        configs = {
            mixed_host: {"cpu_pinning": {"nova": {"value": "4"}},
                         "hugepages": {"nova": {"value": {"2048": 258,
                                                          "1048576": 1}},
                                       "dpdk": {"value": "0"}}},
            one_gb_host: {"cpu_pinning": {"nova": {"value": "4"}},
                          "hugepages": {"nova": {"value": {"2048": 0,
                                                           "1048576": 2}},
                                        "dpdk": {"value": "0"}}},
            two_mb_host: {"cpu_pinning": {"nova": {"value": "4"}},
                          "hugepages": {"nova": {"value": {"2048": 540,
                                                           "1048576": 0}},
                                        "dpdk": {"value": "0"}}},
        }

        # configs = dict(zip(compute_ids, configs))

        # for compute_name, config in configs.items():
        #     compute_id = \
        #         self.fuel_web.get_nailgun_node_by_name(compute_name)['id']
        #     original_config = \
        #         self.fuel_web.client.get_node_attributes(compute_id)
        #     self.fuel_web.client.upload_node_attributes(
        #         utils.dict_merge(original_config, config), compute_id)

        # import ipdb; ipdb.set_trace()

        # self.fuel_web.deploy_cluster_wait(cluster_id)

        for compute in computes:
            config = configs[compute["name"]]
            two_mb_count = config["hugepages"]["nova"]["value"]["2048"]
            one_gb_count = config["hugepages"]["nova"]["value"]["1048576"]

            cmd = ("cat /sys/devices/system/node/node{}/hugepages/"
                   "hugepages-{}kB/nr_hugepages")

            actual_two_mb_count = 0
            actual_one_gb_count = 0

            for numa_node in [0, 1]:
                actual_two_mb_count += int("".join(self.ssh_manager.execute(
                    compute['ip'], cmd.format(numa_node, "2048"))["stdout"]))

                result = "".join(self.ssh_manager.execute(
                    compute['ip'], cmd.format(numa_node, "1048576"))["stdout"])
                result = "0" or result
                actual_one_gb_count += int(result)

            logger.info("{}{}{}{}".format(compute["ip"], " 1Mb: ", two_mb_count, actual_two_mb_count))
            logger.info("{}{}{}{}".format(compute["ip"], " 1Gb: ", one_gb_count, actual_one_gb_count))

        controller_ip = self.fuel_web.get_public_vip(cluster_id)
        comm = common.Common(
            controller_ip,
            settings.SERVTEST_USERNAME,
            settings.SERVTEST_PASSWORD,
            settings.SERVTEST_TENANT)
        self.os_conn = os_actions.OpenStackActions(controller_ip)

        aggregate = comm.nova.aggregates.create(name="hpgs-aggr", availability_zone="nova")
        comm.nova.aggregates.set_metadata(aggregate, metadata={"hpgs": "true", "pinned": "true"})
        comm.nova.aggregates.add_host(aggregate, self.fuel_web.get_nailgun_node_by_name(one_gb_host)['fqdn'])
        comm.nova.aggregates.add_host(aggregate, self.fuel_web.get_nailgun_node_by_name(two_mb_host)['fqdn'])

        aggregate = comm.nova.aggregates.create(name="normal-aggr", availability_zone="nova")
        comm.nova.aggregates.set_metadata(aggregate, metadata={"hpgs": "true"})
        comm.nova.aggregates.add_host(aggregate, self.fuel_web.get_nailgun_node_by_name(mixed_host)['fqdn'])

        flavors = [
            (
                {
                    "name": "h1.huge.hpgs",
                    "ram": 1024,
                    "vcpu": 1,
                    "disk": 1
                },
                {
                    "hw:mem_page_size": 1048576,
                    "aggregate_instance_extra_specs:hpgs": "true",
                    "aggregate_instance_extra_specs:pinned": "true",
                }
            ),
            (
                {
                    "name": "h1.small.hpgs",
                    "ram": 512,
                    "vcpu": 1,
                    "disk": 1
                },
                {
                    "hw:mem_page_size": 2048,
                    "aggregate_instance_extra_specs:hpgs": "true",
                    "aggregate_instance_extra_specs:pinned": "true",
                }
            ),
            (
                {
                     "name": "h1.huge_mixed_host.hpgs",
                     "ram": 1024,
                     "vcpu": 1,
                     "disk": 1
                },
                {
                     "hw:mem_page_size": 1048576,
                     "aggregate_instance_extra_specs:hpgs": "true"
                }
            ),
            (
                {
                     "name": "h1.huge.hpgs",
                     "ram": 512,
                     "vcpu": 1,
                     "disk": 1
                },
                {
                     "hw:mem_page_size": 2048,
                     "aggregate_instance_extra_specs:hpgs": "true"
                }
            )
        ]

        for flavor_params, flavor_extra in flavors:
            flavor = comm.nova.flavors.create(**flavor_params)
            flavor.set_keys(flavor_extra)

        def _get_cirros_image():
            for image in comm.glance.images.list():
                if image.name.startswith("TestVM"):
                    return image

        self.boot_instance_validate(
            "TestHP", "h1.huge.hpgs", _get_cirros_image().id,
            filter(lambda compute: compute["name"] == one_gb_host, computes).pop()['fqdn'],
            1048576)

