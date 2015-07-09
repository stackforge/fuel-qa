from proboscis import test
import os

from fuelweb_test.helpers.decorators import log_snapshot_after_test
from fuelweb_test import settings as CONF
from fuelweb_test.tests import base_test_case


@test(groups=["robustness"])
class BaseRobustnessTest(base_test_case.TestBasic):
    def prepare_rally_container(self, master_node):
        rpm_url = os.getenv('RPM_URL')
        rpm_name = os.getenv('RPM_NAME')
        # copy plugin to the master node
        master_node.execute("wget {0}/{1}".format(rpm_url, rpm_name))
        # install plugin
        master_node.execute("rpm -ihv {0}".format(rpm_name))

    def run_scenario(self, master_node):
        ssh_private_key = os.getenv('SSH_PRIVATE_KEY')
        publish_host = os.getenv('PUBLISH_HOST')
        master_node.execute("rally -s "
                            "power_off_and_on_random_controller.json")
        master_node.execute('scp -i {0} -o StrictHostKeyChecking=no -q -r'
                            'power_off_and_on_random_controller_result.html'
                            ' {1}'.format(ssh_private_key, publish_host))


@test(groups=["haos"])
class Haos(BaseRobustnessTest):
    @test(depends_on=[base_test_case.SetupEnvironment.prepare_slaves_5],
          groups=["haos_test"])
    @log_snapshot_after_test
    def run_haos_test(self):
        """Deploy cluster in ha mode

        Scenario:
            1. Install rally container
            2. Create cluster
            3. Add 3 nodes with controller role
            4. Add 2 nodes with compute role
            5. Deploy the cluster
            6. Run network verification
            7. Run OSTF
            8. Run robustness scenario

        Duration 35m
        """
        self.env.revert_snapshot("ready_with_5_slaves")
        master_node = self.env.d_env.get_admin_remote()
        self.prepare_rally_container(master_node)

        settings = None

        if CONF.NEUTRON_ENABLE:
            settings = {
                "net_provider": 'neutron',
                "net_segment_type": CONF.NEUTRON_SEGMENT_TYPE
            }

        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=CONF.DEPLOYMENT_MODE,
            settings=settings
        )

        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['controller'],
                'slave-03': ['controller'],
                'slave-04': ['compute'],
                'slave-05': ['compute'],
            }
        )

        # Verify network
        self.fuel_web.verify_network(cluster_id)

        self.fuel_web.deploy_cluster_wait(cluster_id)

        # Verify network and run OSTF tests
        self.fuel_web.verify_network(cluster_id)
        self.fuel_web.run_ostf(cluster_id=cluster_id)

        self.run_scenario(master_node)

        self.env.make_snapshot("haos_test")
