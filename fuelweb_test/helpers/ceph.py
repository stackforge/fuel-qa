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

import json

from fuelweb_test import logger

from fuelweb_test.settings import OPENSTACK_RELEASE
from fuelweb_test.settings import OPENSTACK_RELEASE_CENTOS
from fuelweb_test.settings import OPENSTACK_RELEASE_UBUNTU


class CephManager(object):

    supported_distros = (OPENSTACK_RELEASE_CENTOS, OPENSTACK_RELEASE_UBUNTU)

    def __init__(self, remote):
        self.remote = remote

    @classmethod
    def _run_on_remote(cls, remote, cmd):
        """Execute ``cmd`` on ``remote`` and return result.

        :param remote: devops.helpers.helpers.SSHClient
        :param cmd: str
        :return: None
        :raise: DistributionNotSupported
        """
        result = remote.execute(cmd)
        if result['exit_code'] != 0:
            error_msg = (
                "Unable to execute '{0}' on host {0}".format(cmd, remote.host))
            logger.error(error_msg)
            raise Exception(error_msg)
        return result['stdout']

    @classmethod
    def check_distribution(cls):
        """Checks whether distribution is supported.

        List of allowed distrbutions are in ``supported_distros``
        :return: None
        :raise: DistributionNotSupported
        """
        if OPENSTACK_RELEASE not in cls.supported_distros:
            error_msg = (
                "{0} distribution is not supported!".format(OPENSTACK_RELEASE))
            logger.error(error_msg)
            raise Exception(error_msg)

    @classmethod
    def start_monitor(cls, remote):
        """Restarts ceph-mon service depending on Linux distribution.

        :param remote: devops.helpers.helpers.SSHClient
        :return: None
        :raise: DistributionNotSupported
        """
        logger.info("Starting Ceph monitor on %s", remote.host)
        cls.check_distribution()
        if OPENSTACK_RELEASE == OPENSTACK_RELEASE_UBUNTU:
            cls._run_on_remote(remote, 'start ceph-mon-all')
        if OPENSTACK_RELEASE == OPENSTACK_RELEASE_CENTOS:
            cls._run_on_remote(remote, '/etc/init.d/ceph start')

    @classmethod
    def stop_monitor(cls, remote):
        """Restarts ceph-mon service depending on Linux distribution.

        :param remote: devops.helpers.helpers.SSHClient
        :return: None
        :raise: DistributionNotSupported
        """
        logger.info("Stopping Ceph monitor on %s", remote.host)
        cls.check_distribution()
        if OPENSTACK_RELEASE == OPENSTACK_RELEASE_UBUNTU:
            cls._run_on_remote(remote, 'stop ceph-mon-all')
        if OPENSTACK_RELEASE == OPENSTACK_RELEASE_CENTOS:
            cls._run_on_remote(remote, '/etc/init.d/ceph stop')

    @classmethod
    def restart_monitor(cls, remote):
        """Restarts ceph-mon service depending on Linux distribution.

        :param remote: devops.helpers.helpers.SSHClient
        :return: None
        :raise: DistributionNotSupported
        """
        cls.stop_monitor(remote)
        cls.start_monitor(remote)

    @classmethod
    def get_health(cls, remote):
        logger.info("Checking Ceph cluster health on %s", remote.host)
        cmd = 'ceph health -f json'
        result = cls._run_on_remote(remote, cmd)
        return json.loads(''.join(result))

    @classmethod
    def get_status(cls, remote):
        logger.info("Checking Ceph cluster status on %s", remote.host)
        cmd = 'ceph status -f json'
        result = cls._run_on_remote(remote, cmd)
        return json.loads(''.join(result))

    @classmethod
    def get_monitor_node_names(cls, remote):
        """Returns node names with Ceph monitor service is running.

        :param remote: devops.helpers.helpers.SSHClient
        :return: list of node names
        """
        cmd = 'ceph mon_status -f json'
        result = cls._run_on_remote(remote, cmd)
        names = [i['name'] for i in result['monmap']['mons']]
        logger.info("Ceph monitor service is running on %s", ', '.join(names))
        return names

    @classmethod
    def get_node_names_w_time_skew(cls, remote):
        """Returns names of nodes with a time skew.

        :param remote: devops.helpers.helpers.SSHClient
        :return: list of host names
        """
        health = cls.get_health(remote)
        monitors = health['timechecks']['mons']
        names = [i['name'] for i in monitors if i['skew']]
        logger.info("Time skew is found on %s", ', '.join(names))
        return names
