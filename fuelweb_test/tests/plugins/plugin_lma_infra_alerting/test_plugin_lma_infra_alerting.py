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
import os

from proboscis.asserts import assert_equal
from proboscis.asserts import assert_is_not_none
from proboscis.asserts import assert_true
from proboscis import test
import requests

from fuelweb_test import logger
from fuelweb_test import settings as conf
from fuelweb_test.helpers import checkers
from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=["plugins", "lma_plugins"])
class TestLmaInfraAlertingPlugin(TestBasic):
    """Class for testing the LMA infrastructure plugin plugin."""

    @test(depends_on=[SetupEnvironment.prepare_slaves_5],
          groups=["deploy_lma_infra_alerting_ha"])
    @log_snapshot_after_test
    def deploy_lma_infra_alerting_ha(self):
        """Deploy cluster in HA with the LMA infrastructure alerting plugin

        This also deploys the LMA Collector plugin and InfluxDB-Grafana plugin
        since they work together.

        Scenario:
            1. Upload plugins to the master node
            2. Install plugins
            3. Create cluster
            4. Add 3 nodes with controller role
            5. Add 1 node with compute + cinder role
            6. Add 1 node with base-os role
            7. Deploy the cluster
            8. Check that the plugins work
            9. Run OSTF

        Duration 70m
        Snapshot deploy_lma_infra_alerting_ha

        """

        self.env.revert_snapshot("ready_with_5_slaves")

        cluster_id = self._bootstrap('slave-05_base-os')

        self.fuel_web.update_nodes(
            cluster_id,
            {
                "slave-01": ["controller"],
                "slave-02": ["controller"],
                "slave-03": ["controller"],
                "slave-04": ["compute", "cinder"],
                "slave-05": ["base-os"]
            }
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)
        self._check_nagios('slave-05')
        self.fuel_web.run_ostf(cluster_id=cluster_id)
        self.env.make_snapshot("deploy_lma_infra_alerting_ha")

    @test(depends_on=[SetupEnvironment.prepare_slaves_3],
          groups=["deploy_lma_infra_alerting_nonha"])
    @log_snapshot_after_test
    def deploy_lma_infra_alerting_nonha(self):
        """Deploy cluster non HA mode with the LMA infrastructure alerting

        This also deploys the LMA Collector plugin and InfluxDB-Grafana plugin
        since they work together.

        Scenario:
            1. Upload plugins to the master node
            2. Install plugins
            3. Create cluster
            4. Add 1 nodes with controller role
            5. Add 1 node with compute + cinder role
            6. Add 1 node with base-os role
            7. Deploy the cluster
            8. Check that the plugins work

        Duration 70m
        Snapshot deploy_lma_infra_alerting_nonha

        """
        self.env.revert_snapshot("ready_with_3_slaves")

        cluster_id = self._bootstrap('slave-03_base-os')

        self.fuel_web.update_nodes(
            cluster_id,
            {
                "slave-01": ["controller"],
                "slave-02": ["compute", "cinder"],
                "slave-03": ["base-os"]
            }
        )
        self.fuel_web.deploy_cluster_wait(cluster_id)
        self._check_nagios('slave-03')

    def _bootstrap(self, node_user_name):

        # copy plugins to the master node

        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            conf.LMA_COLLECTOR_PLUGIN_PATH, "/var")
        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            conf.LMA_INFRA_ALERTING_PLUGIN_PATH, "/var")
        checkers.upload_tarball(
            self.env.d_env.get_admin_remote(),
            conf.INFLUXDB_GRAFANA_PLUGIN_PATH, "/var")

        # install plugins

        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(conf.LMA_COLLECTOR_PLUGIN_PATH))
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(conf.LMA_INFRA_ALERTING_PLUGIN_PATH))
        checkers.install_plugin_check_code(
            self.env.d_env.get_admin_remote(),
            plugin=os.path.basename(conf.INFLUXDB_GRAFANA_PLUGIN_PATH))

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=conf.DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": conf.NEUTRON_SEGMENT_TYPE,
            }
        )

        plugins = [
            {
                'name': 'lma_collector',
                'options': {
                    'metadata/enabled': True,
                    'environment_label/value': 'deploy_lma_infra_alerting_ha',
                    'elasticsearch_mode/value': 'disabled',
                    'influxdb_mode/value': 'local',
                    'alerting_mode/value': 'local',
                }
            },
            {
                'name': 'lma_infrastructure_alerting',
                'options': {
                    'metadata/enabled': True,
                    'send_to/value': 'root@localhost',
                    'send_from/value': 'nagios@localhost',
                    'smtp_host/value': '127.0.0.1',

                }
            },
            {
                'name': 'influxdb_grafana',
                'options': {
                    'metadata/enabled': True,
                    'node_name/value': node_user_name,
                    'influxdb_rootpass/value': 'r00tme',
                    'influxdb_username/value': 'lma',
                    'influxdb_userpass/value': 'pass',
                    'grafana_username/value': 'grafana',
                    'grafana_userpass/value': 'grafanapass',

                }
            },
        ]
        for plugin in plugins:
            plugin_name = plugin['name']
            msg = "Plugin '%s' couldn't be found. Test aborted" % plugin_name
            assert_true(
                self.fuel_web.check_plugin_exists(cluster_id, plugin_name),
                msg)
            logger.debug('%s plugin is installed' % plugin_name)
            self.fuel_web.update_plugin_data(cluster_id, plugin_name,
                                             plugin['options'])

        return cluster_id

    def _check_nagios(self, node_name, password='r00tme'):
        nagios_node_ip = self.fuel_web.get_nailgun_node_by_name(
            node_name).get('ip')
        assert_is_not_none(
            nagios_node_ip,
            "Fail to retrieve the IP address for slave-05"
        )

        nagios_url = "http://{}:{}".format(nagios_node_ip, '8001')
        r = requests.get(nagios_url, auth=('nagiosadmin', password))
        assert_equal(
            r.status_code, 200,
            "Nagios HTTP response code {}, expected {}".format(
                r.status_code, 200)
        )
