import time
import os
import logging

from devops.helpers.helpers import tcp_ping
from devops.helpers.helpers import wait
import netaddr
from proboscis import test

from fuelweb_test.helpers import decorators
from fuelweb_test.helpers import rally_imlp_http
from fuelweb_test import logger
from fuelweb_test.helpers import nessus
from fuelweb_test import settings as CONF
from fuelweb_test.tests import base_test_case
from fuelweb_test.tests.test_neutron_tun_base import NeutronTunHaBase


@test(groups=["rally"])
class TestRally(NeutronTunHaBase):
    """Security tests by Nessus

    Environment variables:
        - RALLY_DOCKER_HTTP - URL for downloading RPM with rally container.
    """

    def run_container(self, image_name, expose_port_from, expose_port_to,
                      command=None, image_tag="latest", env_vars=None):
        options = ""
        if env_vars is not None:
            for var, value in env_vars.items():
                options += "-e {0}='{1}'".format(var, value)

        cmd = ("docker run -d {env_vars} "
               "-p 0.0.0.0:{expose_to}:{expose_from} "
               "{image_name}:{tag}"
               .format(env_vars=options,
                       expose_to=expose_port_to,
                       expose_from=expose_port_from,
                       image_name=image_name,
                       tag=image_tag))

        if command is not None:
            cmd += ' {0}'.format(command)
        logger.info('Running Rally container {0}'.format(image_name))
        result = self.env.d_env.get_admin_remote().execute(cmd)
        logger.info(result)
        return result

    @test(depends_on=[base_test_case.SetupEnvironment.prepare_slaves_5],
          groups=["deploy_neutron_tun_ha_rally"])
    @decorators.log_snapshot_after_test
    def deploy_neutron_tun_ha_rally(self):
        """Deploy cluster in HA mode with Neutron VXLAN for Rally

        Scenario:
            1. Create cluster
            2. Add 3 nodes with controller role
            3. Add 2 nodes with compute role
            4. Deploy the cluster
            5. Run network verification
            6. Run OSTF

        Duration 80m
        Snapshot deploy_neutron_tun_ha_rally
        """
        super(self.__class__, self).deploy_neutron_tun_ha_base(
            snapshot_name="deploy_neutron_tun_ha_rally")

    @test(depends_on=[deploy_neutron_tun_ha_rally],
          groups=["neutron_tun_rally_6h"])
    def neutron_tun_rally_6h(self):
        """Run rally stability for 6 hours

        Scenario:
            1. Install container with rally & rallyd
            2. Start task
            3. Download task results

        Duration 360m
        """
        self.env.revert_snapshot("deploy_neutron_tun_ha_rally")

        with self.env.d_env.get_admin_remote() as remote:
            remote.execute("wget {0}".format(CONF.RALLY_DOCKER_HTTP))
            remote.execute("rpm -i {0}".format(
                CONF.RALLY_DOCKER_HTTP.split('/')[-1]))

        backend_ips = \
            ('{0}:8888 '.
             format(self.fuel_web.get_nailgun_node_by_name("slave-01")['ip']))
        backend_ips += \
            ('{0}:8888 '.
             format(self.fuel_web.get_nailgun_node_by_name("slave-02")['ip']))
        backend_ips += \
            ('{0}:8888'.
             format(self.fuel_web.get_nailgun_node_by_name("slave-03")['ip']))

        self.run_container(
            "rallyd-isolated",
            expose_port_from=8000,
            expose_port_to=10000,
            env_vars={'BACKEND_IPS': backend_ips})

        rally = rally_imlp_http.RallydClient(
            'http://{0}:20000/'.format(self.fuel_web.admin_node_ip))
        wait(lambda: tcp_ping(self.fuel_web.admin_node_ip, 20000),
             timeout=120)

        cluster_id = self.fuel_web.get_last_created_cluster()
        public_vip = self.fuel_web.get_public_vip(cluster_id)
        deployment = rally.create_deployment(
            auth_url='http://{0}:5000/v2.0/'.format(public_vip),
            username='admin',
            password='admin',
            tenant_name='admin')['deployment']

        scenario_file = ('{0}/fuelweb_test/rally/screnarios/'
                         'nova_boot_server_stability.json'
                         .format(os.environ.get("WORKSPACE", "./")))

        task = rally.create_task(
            scenario_file,
            tag="SystemTest",
            deployment_uuid=deployment['uuid'])['task']
        task_uuid = task['uuid']

        log_lines = [0, 10]
        for handler in logger.handlers:
            handler.setFormatter(logging.Formatter('%(message)s'))

        def poll_task_with_log():
            task = rally.get_task(task_uuid)['task']
            log = rally.get_task_log(
                task_uuid,
                start_line=log_lines[0],
                end_line=log_lines[1])['task_log']

            log_lines[0] = log_lines[1]
            log_lines[1] = (log['total_lines']
                            if log['total_lines'] >= log_lines[1]
                            else log_lines[1])

            for log_line in log['data']:
                logger.info(log_line.strip())
            return task['status'] not in ["init", "verifying",
                                          "setting up", "running"]

        wait(poll_task_with_log, timeout=2000)
        log = rally.get_task_log(task_uuid,
                                 start_line=log_lines[1],
                                 end_line=log_lines[1]+100)['task_log']
        for log_line in log['data']:
            logger.info(log_line.strip())
