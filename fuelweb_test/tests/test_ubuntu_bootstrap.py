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
import random
import tempfile
import textwrap

from devops.helpers.helpers import wait
from proboscis import SkipTest
from proboscis import test
from proboscis.asserts import assert_true, assert_equal, assert_not_equal

from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.helpers.utils import run_on_remote
from fuelweb_test.helpers import fuel_actions
from fuelweb_test.helpers import replace_repos
from fuelweb_test import settings
from fuelweb_test import logger
from fuelweb_test.settings import NEUTRON_SEGMENT_TYPE
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["bvt_ubuntu_bootstrap"])
class UbuntuBootstrapBuild(TestBasic):
    def verify_bootstrap_on_node(self, node):
        logger.info("Verify bootstrap on slaves")
        with self.fuel_web.get_ssh_for_node(node.name) as slave_remote:
            cmd = 'cat /etc/*release'
            output = run_on_remote(slave_remote, cmd)[0].lower()
            assert_true("ubuntu" in output,
                        "Slave {0} doesn't use Ubuntu image for "
                        "bootstrap after Ubuntu images "
                        "were enabled, /etc/release content: {1}"
                        .format(node.name, output))

    @test(depends_on=[SetupEnvironment.prepare_release],
          groups=["prepare_default_ubuntu_bootstrap"])
    @log_snapshot_after_test
    def build_default_bootstrap(self):
        """Verify than slaves retrieved ubuntu bootstrap instead CentOS

        Scenario:
            1. Revert snapshot ready
            2. Choose Ubuntu bootstrap on master node
            3. Bootstrap slaves
            4. Verify bootstrap on slaves

        Duration 15m
        Snapshot: prepare_ubuntu_bootstrap
        """
        self.env.revert_snapshot("ready")

        with self.env.d_env.get_admin_remote() as remote:
            fuel_bootstrap = fuel_actions.FuelBootstrapCliActions(remote)
            uuid, bootstrap_location = fuel_bootstrap.build_bootstrap_image()
            fuel_bootstrap.import_bootstrap_image(bootstrap_location)
            fuel_bootstrap.activate_bootstrap_image(uuid, notify_webui=True)

        self.env.bootstrap_nodes(self.env.d_env.nodes().slaves[:3], skip_timesync=True)
        for node in self.env.d_env.nodes().slaves[:3]:
            self.env.bootstrap_nodes([node])
            self.verify_bootstrap_on_node(node)

        self.env.make_snapshot("prepare_default_ubuntu_bootstrap",
                               is_make=True)

    @test(depends_on=[SetupEnvironment.prepare_release],
          groups=["prepare_simple_ubuntu_bootstrap"])
    @log_snapshot_after_test
    def build_simple_bootstrap(self):
        """Verify than slaves retrieved ubuntu bootstrap instead CentOS

        Scenario:
            1. Revert snapshot ready
            2. Choose Ubuntu bootstrap on master node
            3. Bootstrap slaves
            4. Verify bootstrap on slaves

        Duration 15m
        Snapshot: prepare_ubuntu_bootstrap
        """
        self.env.revert_snapshot("ready")

        with self.env.d_env.get_admin_remote() as remote:
            fuel_bootstrap = fuel_actions.FuelBootstrapCliActions(remote)
            bootstrap_default_params = \
                fuel_bootstrap.get_bootstrap_default_config()

            ubuntu_repo = bootstrap_default_params["ubuntu_repos"][0]["uri"]
            mos_repo = bootstrap_default_params["mos_repos"][0]["uri"]

            bootstrap_params = {
                "ubuntu-release": "trusty",
                "ubuntu-repo": "'{0} trusty'".format(ubuntu_repo),
                "mos-repo": "'{0} mos8.0'".format(mos_repo),
                "label": "UbuntuBootstrap",
                "output-dir": "/tmp",
                "package": ["ipython"]
            }

            uuid, bootstrap_location = \
                fuel_bootstrap.build_bootstrap_image(**bootstrap_params)
            fuel_bootstrap.import_bootstrap_image(bootstrap_location)
            fuel_bootstrap.activate_bootstrap_image(uuid, notify_webui=True)

        self.env.bootstrap_nodes(self.env.d_env.nodes().slaves[:3])
        for node in self.env.d_env.nodes().slaves[:3]:
            self.verify_bootstrap_on_node(node)
            with self.fuel_web.get_ssh_for_node(node.name) as slave_remote:
                ipython_version = checkers.get_package_versions_from_node(
                    slave_remote, name="ipython", os_type="Ubuntu")
                print ipython_version
                print checkers.get_package_versions_from_node(
                    slave_remote, name="ipythonasd", os_type="Ubuntu")
                assert_not_equal(ipython_version, "")

    @test(depends_on=[SetupEnvironment.prepare_release],
          groups=["prepare_full_ubuntu_bootstrap"])
    @log_snapshot_after_test
    def build_full_bootstrap(self):
        """Verify than slaves retrieved ubuntu bootstrap instead CentOS

        Scenario:
            1. Revert snapshot ready
            2. Choose Ubuntu bootstrap on master node
            3. Bootstrap slaves
            4. Verify bootstrap on slaves

        Duration 15m
        Snapshot: prepare_ubuntu_bootstrap
        """
        self.env.revert_snapshot("ready")

        with self.env.d_env.get_admin_remote() as remote:
            fuel_bootstrap = fuel_actions.FuelBootstrapCliActions(remote)
            bootstrap_default_params = \
                fuel_bootstrap.get_bootstrap_default_config()

            ubuntu_repo = bootstrap_default_params["ubuntu_repos"][0]["uri"]
            mos_repo = bootstrap_default_params["mos_repos"][0]["uri"]

            bootstrap_script = '''\
                #!/bin/bash

                echo "testdata" > /test_bootstrap_script
                apt-get install ipython -y'''

            with tempfile.NamedTemporaryFile() as temp_file:
                temp_file.write(textwrap.dedent(bootstrap_script))
                temp_file.flush()
                remote.mkdir("/root/bin")
                remote.upload(temp_file.name, "/root/bin/bootstrap_script.sh")

            remote.mkdir("/root/var/lib/testdir")
            remote.mkdir("/root/var/www/testdir2")

            bootstrap_params = {
                "ubuntu-release": "trusty",
                "ubuntu-repo": "'{0} trusty'".format(ubuntu_repo),
                "mos-repo": "'{0} mos8.0'".format(mos_repo),
                # "http-proxy": "",
                # "https-proxy": "",
                # "direct-repo-addr": "",
                "script": "/root/bin/bootstrap_script.sh",
                "include-kernel-module": "core",
                "blacklist-kernel-module": "fuse",
                "label": "UbuntuBootstrap",
                "inject-files-from": "/root/",
                "extend-kopts": "'biosdevname=0 net.ifnames=1 debug ignore_loglevel log_buf_len=10M'",
                # "kernel-flavor": "",
                "output-dir": "/tmp",
                # "repo": [],
                "package": ["fuse", "sshfs"],
            }

            fuel_bootstrap = fuel_actions.FuelBootstrapCliActions(remote)
            uuid, bootstrap_location = \
                fuel_bootstrap.build_bootstrap_image(**bootstrap_params)
            fuel_bootstrap.import_bootstrap_image(bootstrap_location)
            fuel_bootstrap.activate_bootstrap_image(uuid, notify_webui=True)

        self.env.bootstrap_nodes(self.env.d_env.nodes().slaves[:3], skip_timesync=True)
        for node in self.env.d_env.nodes().slaves[:3]:
            self.verify_bootstrap_on_node(node)
            #TODO: Additional checks

    @test(depends_on_groups=["prepare_default_ubuntu_bootstrap"],
          groups=[""])
    @log_snapshot_after_test
    def create_list_import_delete_bootstrap_image(self):
        self.env.revert_snapshot("prepare_default_ubuntu_bootstrap")

        with self.env.d_env.get_admin_remote() as remote:
            fuel_bootstrap = fuel_actions.FuelBootstrapCliActions(remote)
            bootstrap_location, uuid = \
                fuel_bootstrap.build_bootstrap_image()
            fuel_bootstrap.import_bootstrap_image(bootstrap_location)

            assert_true(uuid in fuel_bootstrap.list_bootstrap_images(), "")
            assert_equal(3, fuel_bootstrap.list_bootstrap_images_uuids(), "")

            fuel_bootstrap.delete_bootstrap_image(uuid)
            assert_true(uuid not in fuel_bootstrap.list_bootstrap_images())
            assert_equal(2, fuel_bootstrap.list_bootstrap_images_uuids())

            uuid = fuel_bootstrap.list_bootstrap_images()
            assert_true("error" in fuel_bootstrap.delete_bootstrap_image(uuid))


@test(groups=["bvt_ubuntu_bootstrap"])
class UbuntuBootstrap(TestBasic):
    def verify_bootstrap_on_node(self, node):
        logger.info("Verify bootstrap on slaves")
        with self.fuel_web.get_ssh_for_node(node.name) as slave_remote:
            cmd = 'cat /etc/*release'
            output = run_on_remote(slave_remote, cmd)[0].lower()
            assert_true("ubuntu" in output,
                        "Slave {0} doesn't use Ubuntu image for "
                        "bootstrap after Ubuntu images "
                        "were enabled, /etc/release content: {1}"
                        .format(node.name, output))

    @test(depends_on_groups=['prepare_default_ubuntu_bootstrap'],
          groups=["deploy_stop_on_deploying_ubuntu_bootstrap"])
    @log_snapshot_after_test
    def deploy_stop_on_deploying_ubuntu_bootstrap(self):
        """Stop reset cluster in HA mode with 1 controller on Ubuntu Bootstrap

        Scenario:
            1. Create cluster in Ha mode with 1 controller
            2. Add 1 node with controller role
            3. Add 1 node with compute role
            4. Verify network
            5. Deploy cluster
            6. Stop deployment
            7. Verify bootstrap on slaves
            8. Add 1 node with cinder role
            9. Re-deploy cluster
            10. Verify network
            11. Run OSTF

        Duration 45m
        Snapshot: deploy_stop_on_deploying_ubuntu_bootstrap
        """

        if not self.env.revert_snapshot('prepare_default_ubuntu_bootstrap'):
            raise SkipTest()

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=settings.DEPLOYMENT_MODE,
            settings={
                'tenant': 'stop_deploy',
                'user': 'stop_deploy',
                'password': 'stop_deploy',
                "net_provider": 'neutron',
                "net_segment_type": NEUTRON_SEGMENT_TYPE
            }
        )
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['compute']
            }
        )
        # Network verification
        self.fuel_web.verify_network(cluster_id)

        # Deploy cluster and stop deployment, then verify bootstrap on slaves
        self.fuel_web.provisioning_cluster_wait(cluster_id)
        self.fuel_web.deploy_task_wait(cluster_id=cluster_id, progress=10)
        self.fuel_web.stop_deployment_wait(cluster_id)
        self.fuel_web.wait_nodes_get_online_state(
            self.env.d_env.nodes().slaves[:2], timeout=10 * 60)
        self.verify_bootstrap_on_slaves(self.env.d_env.nodes().slaves[:3])

        # Network verification
        self.fuel_web.verify_network(cluster_id)

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-03': ['cinder']
            }
        )

        self.fuel_web.deploy_cluster_wait(cluster_id)

        assert_equal(
            3, len(self.fuel_web.client.list_cluster_nodes(cluster_id)))

        # Run ostf
        self.fuel_web.run_ostf(cluster_id=cluster_id,
                               test_sets=['smoke'])

        self.env.make_snapshot(
            "deploy_stop_on_deploying_ubuntu_bootstrap",
            is_make=True)

    @test(depends_on_groups=['deploy_stop_on_deploying_ubuntu_bootstrap'],
          groups=["deploy_reset_on_ready_ubuntu_bootstrap"])
    @log_snapshot_after_test
    def reset_on_ready_ubuntu_bootstrap(self):
        """Stop reset cluster in HA mode with 1 controller on Ubuntu Bootstrap

        Scenario:
            1. Reset cluster
            2. Verify bootstrap on slaves
            3. Re-deploy cluster
            4. Verify network
            5. Run OSTF

        Duration 30m
        """

        if not self.env.revert_snapshot(
                'deploy_stop_on_deploying_ubuntu_bootstrap'):
            raise SkipTest()

        cluster_id = self.fuel_web.get_last_created_cluster()

        # Reset environment,
        # then verify bootstrap on slaves and re-deploy cluster
        self.fuel_web.stop_reset_env_wait(cluster_id)
        self.fuel_web.wait_nodes_get_online_state(
            self.env.d_env.nodes().slaves[:3], timeout=10 * 60)
        self.verify_bootstrap_on_slaves(self.env.d_env.nodes().slaves[:3])

        self.fuel_web.deploy_cluster_wait(cluster_id)

        # Network verification
        self.fuel_web.verify_network(cluster_id)

        # Run ostf
        self.fuel_web.run_ostf(cluster_id=cluster_id,
                               test_sets=['smoke'])

    @test(depends_on_groups=['deploy_stop_on_deploying_ubuntu_bootstrap'],
          groups=["delete_on_ready_ubuntu_bootstrap"])
    @log_snapshot_after_test
    def delete_on_ready_ubuntu_bootstrap(self):
        """Delete cluster cluster in HA mode\
        with 1 controller on Ubuntu Bootstrap

        Scenario:
            1. Delete cluster
            2. Verify bootstrap on slaves

        Duration 30m
        Snapshot: delete_on_ready_ubuntu_bootstrap
        """
        if not self.env.revert_snapshot(
                'deploy_stop_on_deploying_ubuntu_bootstrap'):
            raise SkipTest()

        cluster_id = self.fuel_web.get_last_created_cluster()

        # Delete cluster, then verify bootstrap on slaves
        self.fuel_web.client.delete_cluster(cluster_id)

        # wait nodes go to reboot
        wait(lambda: not self.fuel_web.client.list_nodes(), timeout=10 * 60)

        # wait for nodes to appear after bootstrap
        wait(lambda: len(self.fuel_web.client.list_nodes()) == 3,
             timeout=10 * 60)

        self.verify_bootstrap_on_slaves(self.env.d_env.nodes().slaves[:3])

        self.env.make_snapshot(
            "delete_on_ready_ubuntu_bootstrap",
            is_make=True)

    @test(depends_on_groups=['deploy_stop_on_deploying_ubuntu_bootstrap'],
          groups=["delete_node_on_ready_ubuntu_bootstrap"])
    @log_snapshot_after_test
    def delete_node_on_ready_ubuntu_bootstrap(self):
        """Delete node from cluster in HA mode\
        with 1 controller on Ubuntu Bootstrap

        Scenario:
            1. Delete node
            2. Verify bootstrap on slaves

        Duration 30m
        Snapshot: delete_on_ready_ubuntu_bootstrap
        """
        if not self.env.revert_snapshot(
                'deploy_stop_on_deploying_ubuntu_bootstrap'):
            raise SkipTest()

        cluster_id = self.fuel_web.get_last_created_cluster()

        # Delete cluster, then verify bootstrap on slaves
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-03': ['cinder']
            },
            pending_addition=False,
            pending_deletion=True
        )

        self.fuel_web.run_network_verify(cluster_id)
        self.fuel_web.deploy_cluster_wait(cluster_id, check_services=False)

        # wait for nodes to appear after bootstrap
        wait(lambda: len(self.fuel_web.client.list_nodes()) == 3,
             timeout=10 * 60)

        self.verify_bootstrap_on_slaves(self.env.d_env.nodes().slaves[2])

    @test(depends_on_groups=['deploy_stop_on_deploying_ubuntu_bootstrap'],
          groups=["delete_node_on_ready_ubuntu_bootstrap"])
    def rebootstrap_new_node(self):
        """Delete node from cluster in HA mode\
        with 1 controller on Ubuntu Bootstrap

        Scenario:
            1. Revert snapshot
            2. Build and activate new bootstrap image
            3. Restart unallocated node
            4. Verify new bootstrap

        Duration 30m
        Snapshot: delete_on_ready_ubuntu_bootstrap
        """

        pass
