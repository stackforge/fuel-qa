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

from proboscis.asserts import assert_false
from proboscis import test
from proboscis import SkipTest

from fuelweb_test.helpers.utils import pretty_log
from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import MIRROR_UBUNTU
from fuelweb_test.settings import NEUTRON_SEGMENT
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test import logger


@test(groups=['fuel-mirror'])
class TestUseMirror(TestBasic):
    """Tests custom mirrors to deploy environment.

    Full documentation is in fuel-qa-docs in /doc folder of fuel-qa. It is
    autogenerated and can be found by keyword 'mirror'.

    This test doesn't only checks create mirror utility but also state of our
    mirrors. Most probable problem is absence of packet. It is possible that
    OS now requires new package for bootstrap, or puppet has new dependency
    that is not reflected in our mirror.
    """

    def _get_cluster_repos(self, cluster_id):
        all_repos = self.fuel_web.get_cluster_repos(cluster_id)['value']
        return {
            'ubuntu': [repo for repo in all_repos if 'ubuntu' in repo['name']],
            'mos': [repo for repo in all_repos if 'mos' in repo['name']],
            'all': all_repos}

    def _fix_fuel_mirror_config(self, admin_ip):
        cfg_path = '/usr/share/fuel-mirror/ubuntu.yaml'
        if MIRROR_UBUNTU != '':
            ubuntu_url = MIRROR_UBUNTU.split()[1]
            replace_cmd = \
                "sed -i 's|http://archive.ubuntu.com/ubuntu|{0}|g' {1}"\
                .format(ubuntu_url, cfg_path)
            logger.info(
                'Replacing ubuntu mirrors in the fuel-mirror config with cmd:'
                ' {0}'.format(replace_cmd))
            self.ssh_manager.execute_on_remote(ip=admin_ip,
                                               cmd=replace_cmd)

    @test(groups=['fuel-mirror', 'deploy_with_custom_mirror'],
          depends_on=[SetupEnvironment.prepare_slaves_5])
    def deploy_with_custom_mirror(self):
        """Create local mirrors for Ubuntu repos using fuel-mirror tool

        Scenario:
            1. Create cluster with neutron networking
            2. Add 3 nodes with controller, ceph-osd roles
            3. Add 1 node with cinder, mongo roles
            4. Add 1 node with compute role
            5. Fix fuel-mirror config according to cluster repos
            6. Run create command for Ubuntu mirrors
            7. Run apply command for Ubuntu mirrors
            8. Check that only Ubuntu mirrors were changed
            9. Run create, apply commands for mos mirrors
            10. Run apply command for mos-mirrors
            11. Check than mos mirrors were also changed
            12. Run network verification
            13. Deploy the cluster
            14. Run OSTF
            15. Create snapshot

        Duration 90m
        Snapshot deploy_with_custom_mirror
        """
        self.env.revert_snapshot('ready_with_5_slaves')
        admin_ip = self.ssh_manager.admin_ip

        self.show_step(1, initialize=True)
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": NEUTRON_SEGMENT['tun'],
                'sahara': True,
                'ceilometer': True,
                'volumes_lvm': True,
                'volumes_ceph': False,
                'images_ceph': True
            }
        )

        self.show_step(2)
        self.show_step(3)
        self.show_step(4)
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller', 'ceph-osd'],
                'slave-02': ['controller', 'ceph-osd'],
                'slave-03': ['controller', 'ceph-osd'],
                'slave-04': ['cinder', 'mongo'],
                'slave-05': ['compute']
            }
        )
        self.show_step(5)
        self._fix_fuel_mirror_config(admin_ip)
        cluster_repos = self._get_cluster_repos(cluster_id)
        message = pretty_log({'Cluster repos': cluster_repos['all']})
        logger.info(message)
        self.show_step(6)
        create_cmd = 'fuel-mirror create -P ubuntu -G ubuntu ' \
                     '--log-file /var/log/ubuntu_mirrors_create.log'
        self.ssh_manager.execute_on_remote(ip=admin_ip, cmd=create_cmd)
        self.show_step(7)
        apply_cmd = 'fuel-mirror apply --replace  -P ubuntu -G ubuntu'
        self.ssh_manager.execute_on_remote(ip=admin_ip, cmd=apply_cmd)

        self.show_step(8)

        cluster_repos = self._get_cluster_repos(cluster_id)
        remote_ubuntu_repos = [
            repo for repo in cluster_repos['ubuntu']
            if admin_ip not in repo['uri'] and
            '{settings.MASTER_IP}' not in repo['uri']]
        local_mos_repos = [
            repo for repo in cluster_repos['mos']
            if admin_ip in repo['uri'] or
            '{settings.MASTER_IP}' in repo['uri']]
        repos_log = pretty_log(
            {'All': cluster_repos['all'],
             'Remote Ubuntu': remote_ubuntu_repos,
             'Local MOS:': local_mos_repos})
        logger.info(repos_log)

        assert_false(remote_ubuntu_repos,
                     message="There are some remote Ubuntu repositories: "
                             "{repos}".format(repos=remote_ubuntu_repos))
        # NOTE Main MOS repository is always local in our tests
        assert_false(
            len(local_mos_repos) > 1,
            message="More than one MOS repo became local:{repos}".format(
                repos=local_mos_repos
            )
        )

        self.show_step(9)
        create_cmd = 'fuel-mirror create -P ubuntu -G mos ' \
                     '--log-file /var/log/mos_mirrors_create.log'
        self.env.admin_actions.ensure_cmd(create_cmd)

        self.show_step(10)
        apply_cmd = 'fuel-mirror apply -P ubuntu -G mos'
        self.ssh_manager.execute_on_remote(ip=admin_ip, cmd=apply_cmd)

        self.show_step(11)
        cluster_repos = self._get_cluster_repos(cluster_id)['all']
        remote_repos = [
            repo for repo in cluster_repos
            if admin_ip not in repo['uri'] and
            '{settings.MASTER_IP}' not in repo['uri']]
        message = pretty_log(cluster_repos)
        logger.info(message)
        assert_false(remote_repos,
                     message="There are some remote repositories: "
                             "{repos}".format(repos=remote_repos))

        self.show_step(12)
        self.fuel_web.verify_network(cluster_id)
        self.show_step(13)
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.show_step(14)
        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            test_sets=['ha', 'smoke', 'sanity'])

        self.show_step(15)
        self.env.make_snapshot('deploy_with_custom_mirror')

    # pylint: disable=no-self-use
    @test(groups=['fuel-mirror', 'use-mirror'])
    def deploy_no_official_access(self):
        # TODO(akostrikov) add firewall rules to verify that there is no
        # connection to official mirrors during mirror creation and deployment.
        raise SkipTest('Not implemented yet')

    @test(groups=['fuel-mirror', 'use-mirror'])
    def deploy_with_proxy(self):
        # TODO(akostrikov) add tests to verify that fuel-mirror works with
        # proxies too.
        raise SkipTest('Not implemented yet')
    # pylint: enable=no-self-use