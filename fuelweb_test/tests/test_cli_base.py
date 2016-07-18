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

import time
import json

from proboscis.asserts import assert_equal

from devops.error import TimeoutError
from devops.helpers.helpers import wait
from fuelweb_test.helpers.utils import run_on_remote
from fuelweb_test.helpers.ssl import change_cluster_ssl_config
from fuelweb_test.tests.base_test_case import TestBasic
from fuelweb_test import logwrap
from fuelweb_test import logger
from fuelweb_test.settings import iface_alias
from fuelweb_test.settings import SSL_CN


class CommandLine(TestBasic):
    """CommandLine."""  # TODO documentation

    @logwrap
    def get_task(self, remote, task_id):
        tasks = run_on_remote(remote, 'fuel task --task-id {0} --json'
                              .format(task_id), jsonify=True)
        return tasks[0]

    @logwrap
    def get_network_filename(self, cluster_id, remote):
        cmd = ('fuel --env {0} network --download --dir /tmp --json'
               .format(cluster_id))
        net_download = ''.join(run_on_remote(remote, cmd))
        # net_download = 'Network ... downloaded to /tmp/network_1.json'
        return net_download.split()[-1]

    @logwrap
    def get_networks(self, cluster_id, remote):
        net_file = self.get_network_filename(cluster_id, remote)
        return run_on_remote(remote, 'cat {0}'.format(net_file), jsonify=True)

    @logwrap
    def update_network(self, cluster_id, remote, net_config):
        net_file = self.get_network_filename(cluster_id, remote)
        data = json.dumps(net_config)
        cmd = 'echo {data} > {net_file}'.format(data=json.dumps(data),
                                                net_file=net_file)
        run_on_remote(remote, cmd)
        cmd = ('cd /tmp; fuel --env {0} network --upload --json'
               .format(cluster_id))
        run_on_remote(remote, cmd)

    def assert_cli_task_success(
            self, task, remote, timeout=70 * 60, interval=20):
        logger.info('Wait {timeout} seconds for task: {task}'
                    .format(timeout=timeout, task=task))
        start = time.time()
        try:
            wait(
                lambda: (self.get_task(remote, task['id'])['status'] not in
                         ('pending', 'running')),
                interval=interval,
                timeout=timeout
            )
        except TimeoutError:
            raise TimeoutError(
                "Waiting timeout {timeout} sec was reached for task: {task}"
                .format(task=task["name"], timeout=timeout))
        took = time.time() - start
        task = self.get_task(remote, task['id'])
        logger.info('Task finished in {took} seconds with the result: {task}'
                    .format(took=took, task=task))
        assert_equal(
            task['status'], 'ready',
            "Task '{name}' has incorrect status. {} != {}".format(
                task['status'], 'ready', name=task["name"]
            )
        )

    @logwrap
    def update_cli_network_configuration(self, cluster_id, remote):
        """Update cluster network settings with custom configuration.
        Place here an additional config changes if needed (e.g. nodegroups'
        networking configuration.
        Also this method checks downloading/uploading networks via cli.
        """
        net_config = self.get_networks(cluster_id, remote)
        new_settings = net_config
        self.update_network(cluster_id, remote, new_settings)

    def get_public_vip(self, cluster_id, remote):
        networks = self.get_networks(cluster_id, remote)
        return networks['public_vip']

    def download_settings(self, cluster_id, remote):
        cmd = ('fuel --env {0} settings --download --dir /tmp --json'.format(
            cluster_id))
        run_on_remote(remote, cmd)
        return run_on_remote(remote,
                             'cd /tmp && cat settings_{0}.json'.format(
                                 cluster_id), jsonify=True)

    def upload_settings(self, cluster_id, remote, settings):
        data = json.dumps(settings)
        cmd = 'cd /tmp && echo {data} > settings_{id}.json'.format(
            data=json.dumps(data),
            id=cluster_id)
        run_on_remote(remote, cmd)
        cmd = ('fuel --env {0} settings --upload --dir /tmp --json'.format(
            cluster_id))
        run_on_remote(remote, cmd)

    @logwrap
    def update_ssl_configuration(self, cluster_id, remote):
        settings = self.download_settings(cluster_id, remote)
        change_cluster_ssl_config(settings, SSL_CN)
        self.upload_settings(cluster_id, remote, settings)

    def add_nodes_to_cluster(
            self, remote, cluster_id, node_ids, roles):
        if isinstance(node_ids, int):
            node_ids_str = str(node_ids)
        else:
            node_ids_str = ','.join(str(n) for n in node_ids)
        cmd = ('fuel --env-id={0} node set --node {1} --role={2}'.format(
            cluster_id, node_ids_str, ','.join(roles)))
        run_on_remote(remote, cmd)

    @logwrap
    def use_ceph_for_volumes(self, cluster_id, remote):
        settings = self.download_settings(cluster_id, remote)
        settings['editable']['storage']['volumes_lvm'][
            'value'] = False
        settings['editable']['storage']['volumes_ceph'][
            'value'] = True
        self.upload_settings(cluster_id, remote, settings)

    @logwrap
    def use_ceph_for_images(self, cluster_id, remote):
        settings = self.download_settings(cluster_id, remote)
        settings['editable']['storage']['images_ceph'][
            'value'] = True
        self.upload_settings(cluster_id, remote, settings)

    @logwrap
    def use_ceph_for_ephemeral(self, cluster_id, remote):
        settings = self.download_settings(cluster_id, remote)
        settings['editable']['storage']['ephemeral_ceph'][
            'value'] = True
        self.upload_settings(cluster_id, remote, settings)

    @logwrap
    def change_osd_pool_size(self, cluster_id, remote, replication_factor):
        settings = self.download_settings(cluster_id, remote)
        settings['editable']['storage']['osd_pool_size'][
            'value'] = replication_factor
        self.upload_settings(cluster_id, remote, settings)

    @logwrap
    def use_radosgw_for_objects(self, cluster_id, remote):
        settings = self.download_settings(cluster_id, remote)
        ceph_for_images = settings['editable']['storage']['images_ceph'][
            'value']
        if ceph_for_images:
            settings['editable']['storage']['objects_ceph'][
                'value'] = True
        else:
            settings['editable']['storage']['images_ceph'][
                'value'] = True
            settings['editable']['storage']['objects_ceph'][
                'value'] = True
        self.upload_settings(cluster_id, remote, settings)

    @logwrap
    def download_node_interfaces(self, node_id):
        cmd = ' fuel node --node-id {} --network --download --dir' \
              ' /tmp --json'.format(node_id)
        self.ssh_manager.execute_on_remote(
            ip=self.ssh_manager.admin_ip,
            cmd=cmd
        )
        out = self.ssh_manager.execute_on_remote(
            ip=self.ssh_manager.admin_ip,
            cmd='cd /tmp && cat node_{}/interfaces.json'.format(node_id),
            jsonify=True
        )['stdout_json']
        return out

    def upload_node_interfaces(self, node_id, interfaces):
        data = json.dumps(interfaces)
        cmd = 'cd /tmp && echo {data} > node_{id}/interfaces.json'.format(
            data=json.dumps(data),
            id=node_id)
        self.ssh_manager.execute_on_remote(
            ip=self.ssh_manager.admin_ip,
            cmd=cmd
        )
        cmd = ('fuel node --node-id {} --network --upload --dir /tmp'
               ' --json'.format(node_id))
        self.ssh_manager.execute_on_remote(
            ip=self.ssh_manager.admin_ip,
            cmd=cmd
        )

    @logwrap
    def update_node_interfaces(self, node_id):
        interfaces = self.download_node_interfaces(node_id)
        logger.debug("interfaces we get {}".format(interfaces))
        assigned_networks = {
            iface_alias('eth0'): [{'id': 1, 'name': 'fuelweb_admin'}],
            iface_alias('eth1'): [{'id': 2, 'name': 'public'}],
            iface_alias('eth2'): [{'id': 3, 'name': 'management'}],
            iface_alias('eth3'): [{'id': 5, 'name': 'private'}],
            iface_alias('eth4'): [{'id': 4, 'name': 'storage'}],
        }
        for interface in interfaces:
            name = interface['name']
            net_to_assign = assigned_networks.get(name, None)
            if net_to_assign:
                interface['assigned_networks'] = net_to_assign
        logger.debug("interfaces after update {}".format(interfaces))
        self.upload_node_interfaces(node_id, interfaces)