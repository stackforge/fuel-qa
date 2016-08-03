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

import os
from proboscis.asserts import assert_equal

from fuelweb_test import logger
from fuelweb_test import settings
from fuelweb_test.helpers.utils import install_pkg_2
from fuelweb_test.helpers.ssh_manager import SSHManager


def collect_logs(path,
                 name,
                 nodes=None,
                 include_path=None,
                 filter=None,
                 date_filter=None,
                 store_on_master=settings.STORE_LOG_SNAPSHOT_ON_MASTER):
    '''
    :param path:
    :param name:
    :param nodes:
    :param include_path:
    :param filter:
    :param date_filter:
    :param store_on_master:
    :return: String path to logs
    '''

    timmy = Timmy()


    timmy_ver = timmy.get_timmy_version()
    if not timmy_ver:
        timmy.setup_timmy()
    else:
        logger.info("Timmy v{} log collector found and ready".format(timmy_ver))

    remote_logs_path = os.path.join(settings.TIMMY_LOG_PATH, '{}.tar.gz'.format(name))
    res = timmy.run_timmy(dest_file=remote_logs_path)
    logger.info(res['stdout_str'])

    ssh_manager = SSHManager()
    ssh_manager.download_from_remote(ssh_manager.admin_ip,
                                          remote_logs_path,
                                          path)
    if not store_on_master:
        ssh_manager.check_call(ssh_manager.admin_ip,
                                    'rm {}'.format(remote_logs_path))

    return os.path.join(path, os.path.basename(remote_logs_path))

class Timmy():
    def __init__(self):
        self.ssh_manager = SSHManager()
        self.timmy_path = settings.TIMMY_PATH
        if settings.TIMMY_PATH.startswith('http'):
            # override bin path when install from pip
            self.timmy_path = '/root/timmy'
        self.ready = False

    def setup_timmy(self):
        ver = self.get_timmy_version()
        if not ver:
            self.ready = False
            logger.warning('Timmy are not ready')
        else:
            self.ready = True
            logger.info(
                "Timmy v{} log collector installed and ready".format(ver))

        if not self.ready:
            # install prerequisites
            pkgs = ['git', 'python-pip']
            for pkg in pkgs:
                exit_code = install_pkg_2(
                    ip=self.ssh_manager.admin_ip,
                    pkg_name=pkg)
                assert_equal(0, exit_code, 'Cannot install package {0} '
                                           'on admin node.'.format(pkg))

            # clone repo
            cmd = []
            cmd.append('cd /root')
            cmd.append('git clone -b master {} timmy'.format(settings.TIMMY_PATH))
            cmd.append('cd timmy')
            cmd.append('pip install -e .')
            self.ssh_manager.check_call(self.ssh_manager.admin_ip, ' && '.join(cmd))

            self.ready = True

        else:
            ver = self.get_timmy_version()
            logger.info(
                "Timmy v{} log collector installed and ready".format(ver))

    def get_timmy_version(self):

        res = self.run_timmy(version=True, raise_on_err=False)
        if res['exit_code']!=0:
            return False
        return res['stdout_str']

    def run_timmy(self, raise_on_err=True, dest_file=None, env_id=None, node_ids=None, roles=None,
                  days=None, store_logs=None, get_logs = None,
                  logs_no_default=None, only_logs=None,
                  fuel_ip=None, fuel_user=None, fuel_password=None, version=None):
        """Collect logs

        :param
        :param
        :return String path to tar
        """

        params = []
        if dest_file:
            params.append('--dest-file {}'.format(dest_file))
        if env_id:
            params.append('--env {}'.format(env_id))
        if node_ids:
            for node_id in node_ids:
                params.append('--id {}'.format(node_id))
        if roles:
            for role in roles:
                params.append('--id {}'.format(role))
        if days:
            params.append('--days {}'.format(days))
        if store_logs:
            params.append('--logs')
        if get_logs:
            for get_log in get_logs:
                params.append('--get-logs {} {} {}'.format(
                    get_log['path'],
                    get_log['include'],
                    get_log['exclude']
                ))
        if logs_no_default:
            params.append('--logs-no-default')
        if fuel_ip:
            params.append('--fuel-ip {}'.format(fuel_ip))
        if fuel_user:
            params.append('--fuel-user {}'.format(fuel_user))
        if fuel_password:
            params.append('--fuel-password {}'.format(fuel_password))
        if only_logs:
            params.append('--only-logs')
        if version:
            params.append('--version')

        cmd = 'cd {} && python timmy.py {}'.format(self.timmy_path, ' '.join(params))
        result = self.ssh_manager.check_call(ip=self.ssh_manager.admin_ip, command=cmd, raise_on_err = raise_on_err)
        return result