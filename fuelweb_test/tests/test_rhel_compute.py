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

from __future__ import division

from devops.helpers.helpers import _tcp_ping
from devops.helpers.helpers import wait
from proboscis import asserts
from proboscis import test

from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.helpers import os_actions
from fuelweb_test import settings
from fuelweb_test import logger as LOGGER
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["rhel", "rhel_ha", "rhel.basic"])
class RhelHA(TestBasic):
    """RHEL-based compute tests"""

    def wait_for_slave_provision(self, slave_name, timeout=10 * 60):
        node = self.env.d_env.get_node(name=slave_name)
        node_ip = node.get_ip_address_by_network_name(self.env.d_env.admin_net)
        wait(lambda: _tcp_ping(node_ip, 22),
             timeout=timeout, timeout_msg="Node doesn't appear in network")

    @staticmethod
    def connect_rhel_image(slave):
        """Upload RHEL image into target node

        :param slave: Target node name
        """
        path = settings.RHEL_IMAGE_PATH + settings.RHEL_IMAGE
        if settings.COMPUTE_BOOT_STRATEGY == 'usb':
            slave.disk_devices.get(
                device='disk', bus='usb').volume.upload(path)
            vol_path = slave.disk_devices.get(
                device='disk', bus='usb').volume.get_path()
        elif settings.COMPUTE_BOOT_STRATEGY == 'cdrom':
            slave.disk_devices.get(
                device='cdrom').volume.upload(path)
            vol_path = slave.disk_devices.get(
                device='cdrom').volume.get_path()
        else:
            slave.disk_devices.get(
                name='system').volume.upload(path)
            vol_path = slave.disk_devices.get(name='system').volume.get_path()
        if settings.RHEL_IMAGE_PATH not in vol_path:
            LOGGER.debug("Volume path: {0}".format(vol_path))
            LOGGER.debug("Image path: {0}".format(settings.RHEL_IMAGE_PATH))
            raise Exception("Volume doesn't uploaded")

    @staticmethod
    def register_rhel_subscription(remote):
        """Register RHEL subscription.

        :param remote: Remote node to proceed.
        """
        reg_command = (
            "/usr/sbin/subscription-manager register "
            "--username={0} --password={1} --serverurl={2} "
            "--org={3} --release={4}".format(
                settings.RHEL_LICENSE_USERNAME,
                settings.RHEL_LICENSE_PASSWORD,
                settings.RHEL_SERVER_URL,
                settings.RHEL_REGISTERED_ORG_NAME,
                settings.RHEL_RELEASE)
        )

        if settings.RHEL_ACTIVATION_KEY:
            reg_command = reg_command + "--activationkey={0}".format(
                settings.RHEL_ACTIVATION_KEY)

        result = remote.execute(reg_command)
        LOGGER.debug(result)
        asserts.assert_equal(result['exit_code'], 0, 'RHEL registation failed')

    @staticmethod
    def enable_rhel_repos(remote):
        """Enable Red Hat mirrors on node.

        :param remote: Remote node for proceed
        """
        cmd = ("yum-config-manager --enable rhel-7-server-optional-rpms && "
               "yum-config-manager --enable rhel-7-server-extras-rpms &&"
               "yum-config-manager --enable rhel-7-server-rh-common-rpms")

        result = remote.execute(cmd)
        LOGGER.debug(result)
        asserts.assert_equal(result['exit_code'], 0,
                             'Enabling RHEL repos failed')

    @staticmethod
    def set_hostname(remote):
        """Set hostname with domain for node.

        :param remote: Remote node for proceed
        """
        cmd = "sysctl kernel.hostname=rhel.domain.local"

        result = remote.execute(cmd)
        LOGGER.debug(result)
        asserts.assert_equal(result['exit_code'], 0,
                             'Setting up hostname for node failed')

    @staticmethod
    def apply_compute_puppet(remote):
        puppet_path = [
            "/etc/puppet/modules/osnailyfacter/modular/hiera/hiera.pp",
            "/etc/puppet/modules/osnailyfacter/modular/globals/globals.pp",
            "/etc/puppet/modules/osnailyfacter/modular/firewall/firewall.pp",
            "/etc/puppet/modules/osnailyfacter/modular/tools/tools.pp",
            "/etc/puppet/modules/osnailyfacter/modular/netconfig/netconfig.pp",
            "/etc/puppet/modules/osnailyfacter/modular/roles/compute.pp",
            "/etc/puppet/modules/osnailyfacter/modular/"
            "openstack-network/common-config.pp",
            "/etc/puppet/modules/osnailyfacter/modular/"
            "openstack-network/plugins/ml2.pp",
            "/etc/puppet/modules/osnailyfacter/modular/"
            "openstack-network/agents/l3.pp",
            "/etc/puppet/modules/osnailyfacter/modular/"
            "openstack-network/agents/metadata.pp",
            "/etc/puppet/modules/osnailyfacter/modular/"
            "openstack-network/compute-nova.pp"]

        for puppet in puppet_path:
            result = remote.execute("puppet apply -vd {0}".format(puppet))
            LOGGER.debug(result)
            asserts.assert_equal(result['exit_code'], 0, 'Puppet run failed')

    @staticmethod
    def backup_required_information(remote, ip):
        """Back up required information for compute from target node

        :param remote: Remote Fuel master node
        :param ip: Target node ip to back up from
        """
        LOGGER.debug('Target node ip: {0}'.format(ip))
        cmd = ("cd ~/ && mkdir rhel_backup; "
               "scp -r {0}:/root/.ssh rhel_backup/. ; "
               "scp {0}:/etc/astute.yaml rhel_backup/ ; "
               "scp -r {0}:/var/lib/astute/nova rhel_backup/").format(ip)
        result = remote.execute(cmd)
        LOGGER.debug(result['stdout'])
        LOGGER.debug(result['stderr'])
        asserts.assert_equal(result['exit_code'], 0,
                             'Can not back up required information from node')
        LOGGER.debug("Backed up ssh-keys and astute.yaml")

    @staticmethod
    def restore_information(ip, remote_admin, remote_slave):
        """Restore information on target node

        :param ip: Remote node ip
        :param remote_admin: Remote admin node for proceed
        :param remote_slave: Remote slave node for proceed
        """
        cmd = (
            "cd ~/rhel_backup && "
            "scp -r .ssh {0}:{1}@{2}:/root/. && "
            "scp astute.yaml {0}:{1}@{2}:/etc/.".format(
                settings.RHEL_IMAGE_USER,
                settings.RHEL_IMAGE_PASSWORD,
                ip)
        )

        LOGGER.debug("Restoring ssh-keys and astute.yaml for"
                     " node with ip {0}".format(ip))
        result = remote_admin.execute(cmd)
        LOGGER.debug(result)
        asserts.assert_equal(result['exit_code'], 0,
                             'Can not restore ssh-keys and astute.yaml')

        cmd = "mkdir -p /var/lib/astute"
        LOGGER.debug("Prepare node for restoring nova ssh-keys")
        result = remote_slave.execute(cmd)
        LOGGER.debug(result)
        asserts.assert_equal(result['exit_code'], 0, 'Preparation failed')

        cmd = ("cd ~/rhel_backup && "
               "scp -r nova {0}:{1}@{2}:/var/lib/astute/")
        LOGGER.debug("Restoring nova ssh-keys")
        result = remote_admin.execute(cmd)
        LOGGER.debug(result)
        asserts.assert_equal(result['exit_code'], 0,
                             'Can not restore ssh-keys for nova')

    @staticmethod
    def set_repo_for_perestroika(remote):
        """Set Perestroika repos

        :param remote: Remote node for proceed
        """
        cmd = ("curl https://perestroika-repo-tst.infra.mirantis.net/"
               "mos-repos/centos/mos8.0-centos7-fuel/os/x86_64/")

        result = remote.execute(cmd)
        asserts.assert_equal(result['exit_code'], 0,
                             'Perestroika repos unavailable from node')
        cmd = ("echo '[mos-8.0]\n"
               "name=mos-8.0\n"
               "type=rpm-md\n"
               "baseurl="
               "http://perestroika-repo-tst.infra.mirantis.net/"
               "mos-repos/centos/mos8.0-centos7-fuel/os/x86_64/\n"
               "gpgcheck=1\n"
               "enabled=1\n"
               "priority=5' >>"
               "/etc/yum.repos.d/mos8.0.repo && "
               "yum install yum-utils -y")
        result = remote.execute(cmd)
        LOGGER.debug(result)
        asserts.assert_equal(result['exit_code'], 0,
                             'Can not create config file for repo')

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_rhel_compute_ha_tun"])
    @log_snapshot_after_test
    def deploy_rhel_based_compute(self):
        """Deploy RHEL-based compute in HA mode with Neutron VXLAN

        Scenario:
            1. Check required image.
            2. Revert snapshot 'ready_with_5_slaves'.
            3. Create a Fuel cluster.
            4. Update cluster nodes with required roles.
            5. Deploy the Fuel cluster.
            6. Run OSTF.
            7. Backup astute.yaml and ssh keys from compute.
            8. Boot compute with RHEL image.
            9. Prepare node for Puppet run.
            10. Execute modular tasks for compute.
            11. Run OSTF.

        Duration: 150m
        Snapshot: deploy_rhel_compute_ha_tun

        """
        self.show_step(1)
        LOGGER.debug('Check MD5 sum of RHEL 7 image')
        check_image = checkers.check_image(
            settings.RHEL_IMAGE,
            settings.RHEL_IMAGE_MD5,
            settings.RHEL_IMAGE_PATH)
        asserts.assert_true(check_image)

        self.show_step(2)
        self.env.revert_snapshot("ready_with_5_slaves")

        self.show_step(3)
        LOGGER.debug('Create Fuel cluster RHEL-based compute tests')
        data = {
            'net_provider': 'neutron',
            'net_segment_type': settings.NEUTRON_SEGMENT['tun'],
            'tenant': 'RhelHA',
            'user': 'RhelHA',
            'password': 'RhelHA'
        }
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=settings.DEPLOYMENT_MODE,
            settings=data
        )

        self.show_step(4)
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['controller'],
                'slave-03': ['controller'],
                'slave-04': ['compute']
            }
        )

        self.show_step(5)
        self.fuel_web.deploy_cluster_wait(cluster_id)

        cluster_vip = self.fuel_web.get_public_vip(cluster_id)
        os_conn = os_actions.OpenStackActions(
            cluster_vip, data['user'], data['password'], data['tenant'])
        self.fuel_web.assert_cluster_ready(os_conn, smiles_count=13)

        self.show_step(6)
        self.fuel_web.run_ostf(cluster_id=cluster_id,
                               test_sets=['ha', 'smoke', 'sanity'])

        self.show_step(7)
        compute = self.fuel_web.get_nailgun_cluster_nodes_by_roles(
            cluster_id, ['compute'])[0]
        target_node_name = compute['name'].split('_')[0]
        target_node = self.env.d_env.get_node(name=target_node_name)
        target_node_ip = self.fuel_web.get_nailgun_node_by_name(
            target_node_name)['ip']

        with self.env.d_env.get_admin_remote() as remote:
            self.backup_required_information(remote, target_node_ip)

        self.show_step(8)

        target_node.destroy()
        self.connect_rhel_image(target_node)
        target_node.start()
        self.wait_for_slave_provision(target_node_name)

        self.show_step(9)

        with self.env.d_env.get_admin_remote() as remote_admin:
            with self.env.d_env.get_ssh_to_remote(target_node_ip) as \
                    remote_slave:
                self.restore_information(target_node_ip,
                                         remote_admin, remote_slave)

        with self.env.d_env.get_ssh_to_remote(target_node_ip) as remote:
            self.set_hostname(remote)
            self.set_repo_for_perestroika(remote)

        # Remove this parameter after infrastructure and tests will be ready.
            if not settings.CENTOS_DUMMY_DEPLOY:
                self.register_rhel_subscription(remote)
                self.enable_rhel_repos(remote)

        puppet_install_cmd = "sudo yum install puppet ruby -y"
        with self.env.d_env.get_ssh_to_remote(target_node_ip) as remote:
            result = remote.execute(puppet_install_cmd)
            LOGGER.debug(result)
            if result['exit_code'] != 0:
                raise Exception('Ruby and puppet installation failed')

        with self.env.d_env.get_ssh_to_remote(target_node_ip) as remote:
            cmd = ("rm -f /etc/selinux/config; "
                   "echo 'SELINUX=disabled\n"
                   "SELINUXTYPE=targeted\n"
                   "SETLOCALDEFS=0' > /etc/selinux/config")
            result = remote.execute(cmd)
            LOGGER.debug(result)
            if result['exit_code'] != 0:
                raise Exception('SELinux was not disabled on node.')

        cmd = ("rsync -avz /etc/puppet/modules/* "
               "{0}@{1}:/etc/puppet/modules/".format(settings.RHEL_IMAGE_USER,
                                                     target_node_ip))
        with self.env.d_env.get_admin_remote() as remote:
            remote.execute(cmd)
            LOGGER.debug(cmd)
            if result['exit_code'] != 0:
                raise Exception('Rsync puppet modules failed')

        self.show_step(10)
        with self.env.d_env.get_admin_remote() as remote:
            self.apply_compute_puppet(remote)
        self.fuel_web.assert_cluster_ready(os_conn, smiles_count=13)

        self.show_step(11)
        self.fuel_web.run_ostf(cluster_id=cluster_id,
                               test_sets=['ha', 'smoke', 'sanity'])

        self.env.make_snapshot("ready_ha_with_rhel_compute", is_make=True)
