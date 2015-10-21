#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE_2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import time

from devops.helpers.helpers import wait

from fuelweb_test.helpers.utils import run_on_remote_get_results
from fuelweb_test.helpers.pacemaker import get_pacemaker_nodes_attributes
from fuelweb_test.helpers.pacemaker import get_pcs_nodes
from fuelweb_test.helpers.pacemaker import get_pcs_status_xml


from system_test.tests import actions_base
from system_test.helpers.decorators import make_snapshot_if_step_fail
from system_test.helpers.decorators import deferred_decorator

from system_test import logger


class FillRootBaseActions(actions_base.ActionsBase):

    def __init__(self, config=None):
        super(FillRootBaseActions, self).__init__(config)
        self.ostf_tests_should_failed = 0

    @deferred_decorator([make_snapshot_if_step_fail])
    def _action_get_pcs_initial_state(self,):
        """get controllers initial status in pacemaker"""

        self.primary_controller = self.fuel_web.get_nailgun_primary_node(
            self.env.d_env.nodes().slaves[0])

        self.primary_controller_fqdn = str(
            self.fuel_web.fqdn(self.primary_controller))

        pcs_status_xml = get_pcs_status_xml(self.primary_controller.name)

        with self.fuel_web.get_ssh_for_node(
                self.primary_controller.name) as remote:
            root_free = run_on_remote_get_results(
                remote, 'cibadmin --query --scope status')['stdout_str']

        self.primary_controller_space_on_root = get_pacemaker_nodes_attributes(
            root_free)[self.primary_controller_fqdn]['root_free']

        self.primary_controller_space_to_filled = str(
            int(self.primary_controller_space_on_root) - 80)

        self.pcs_status = get_pcs_nodes(pcs_status_xml)

        self.slave_node_fqdn = list(
            set(self.pcs_status.keys()).difference(
                set(self.primary_controller_fqdn)))[1]

        self.slave_node_running_resources = self.pcs_status[
            self.slave_node_fqdn]['resources_running']

    @deferred_decorator([make_snapshot_if_step_fail])
    def _action_fill_root(self):
        """filling root filesystem on primary controller
        and check pacemaker and cibadmin status"""

        self.ostf_tests_should_failed += 1

        logger.info(
            "Free space in root on primary controller - {}".format(
                self.primary_controller_space_on_root
            ))

        logger.info(
            "Need to fill space on root - {}".format(
                self.primary_controller_space_to_filled
            ))

        with self.fuel_web.get_ssh_for_node(
                self.primary_controller.name) as remote:
            run_on_remote_get_results(
                remote, 'fallocate -l {}M /root/bigfile'.format(
                    self.primary_controller_space_to_filled))

        time.sleep(120)

    @deferred_decorator([make_snapshot_if_step_fail])
    def _action_check_stopping_resources(self):
        """filling root filesystem on primary controller
        and check pacemaker and cibadmin status"""

        with self.fuel_web.get_ssh_for_node(
                self.primary_controller.name) as remote:

            def checking_health_disk_attribute():
                logger.info("Checking for '#health_disk' attribute")
                cibadmin_status_xml = run_on_remote_get_results(
                    remote, 'cibadmin --query --scope status')[
                    'stdout_str']
                pcs_attribs = get_pacemaker_nodes_attributes(
                    cibadmin_status_xml)
                return '#health_disk' in pcs_attribs[
                    self.primary_controller_fqdn]

            def checking_for_red_in_health_disk_attribute():
                logger.info(
                    "Checking for '#health_disk' attribute have 'red' value")
                cibadmin_status_xml = run_on_remote_get_results(
                    remote, 'cibadmin --query --scope status')[
                    'stdout_str']
                pcs_attribs = get_pacemaker_nodes_attributes(
                    cibadmin_status_xml)
                return pcs_attribs[self.primary_controller_fqdn][
                    '#health_disk'] == 'red'

            def check_stopping_resources():
                logger.info(
                    "Checking for 'running_resources "
                    "attribute have '0' value")
                pcs_status_xml = run_on_remote_get_results(
                    remote, 'pcs status xml')['stdout_str']
                pcs_attribs = get_pcs_nodes(pcs_status_xml)
                return pcs_attribs[self.primary_controller_fqdn][
                    'resources_running'] == '0'

            wait(checking_health_disk_attribute,
                 "Attribute #health_disk wasn't appeared "
                 "in attributes on node {} in {} seconds".format(
                     self.primary_controller_fqdn, 300), timeout=5 * 60)

            wait(checking_for_red_in_health_disk_attribute,
                 "Attribute #health_disk doesn't have 'red' value "
                 "on node {} in {} seconds".format(
                     self.primary_controller_fqdn, 300), timeout=5 * 60)

            wait(check_stopping_resources,
                 "Attribute 'running_resources' doesn't have '0' value "
                 "on node {} in {} seconds".format(
                     self.primary_controller_fqdn, 300), timeout=5 * 60)

    @deferred_decorator([make_snapshot_if_step_fail])
    def _action_resolve_space_on_root(self):
        """free space on root filesystem on primary controller
        and check pacemaker and cibadmin status"""

        self.ostf_tests_should_failed -= 1

        with self.fuel_web.get_ssh_for_node(
                self.primary_controller.name) as remote:
            run_on_remote_get_results(remote, 'rm /root/bigfile')

            run_on_remote_get_results(
                remote,
                'crm node status-attr <hostname> delete "#health_disk"'.format(
                    self.primary_controller_fqdn))

        time.sleep(120)

    @deferred_decorator([make_snapshot_if_step_fail])
    def _action_check_starting_resources(self):
        """free space on root filesystem on primary controller
        and check pacemaker and cibadmin status"""

        with self.fuel_web.get_ssh_for_node(
                self.primary_controller.name) as remote:

            def checking_health_disk_attribute_is_not_present():
                logger.info(
                    "Checking for '#health_disk' attribute "
                    "is not present on node {}".format(
                        self.primary_controller_fqdn))
                cibadmin_status_xml = run_on_remote_get_results(
                    remote, 'cibadmin --query --scope status')[
                    'stdout_str']
                pcs_attribs = get_pacemaker_nodes_attributes(
                    cibadmin_status_xml)
                return '#health_disk' not in pcs_attribs[
                    self.primary_controller_fqdn]

            def check_started_resources():
                logger.info(
                    "Checking for 'running_resources' attribute "
                    "have {} value on node {}".format(
                        self.slave_node_running_resources,
                        self.primary_controller_fqdn))
                pcs_status_xml = run_on_remote_get_results(
                    remote, 'pcs status xml')['stdout_str']
                pcs_attribs = get_pcs_nodes(pcs_status_xml)
                return pcs_attribs[self.primary_controller_fqdn][
                    'resources_running'] == self.slave_node_running_resources

            wait(checking_health_disk_attribute_is_not_present,
                 "Attribute #health_disk was appeared in attributes "
                 "on node {} in {} seconds".format(
                     self.primary_controller_fqdn, 300), timeout=5 * 60)

            wait(check_started_resources,
                 "Attribute 'running_resources' doesn't have {} value "
                 "on node {} in {} seconds".format(
                     self.slave_node_running_resources,
                     self.primary_controller_fqdn, 300), timeout=5 * 60)
