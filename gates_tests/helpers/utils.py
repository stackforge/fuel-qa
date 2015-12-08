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


from proboscis.asserts import assert_equal

from fuelweb_test.helpers import checkers

from fuelweb_test import logger
from fuelweb_test import settings


def replace_fuel_agent_rpm(environment):
    """Replaced fuel_agent*.rpm in MCollective with fuel_agent*.rpm
    from review
    environment - Environment Model object - self.env
    """
    logger.info("Patching fuel-agent")
    if not settings.UPDATE_FUEL:
        raise Exception("{} variable don't exist"
                        .format(settings.UPDATE_FUEL))
    try:
        pack_path = '/var/www/nailgun/fuel-agent/'
        container = 'mcollective'
        with environment.d_env.get_admin_remote() as remote:
            remote.upload(settings.UPDATE_FUEL_PATH.rstrip('/'),
                          pack_path)

        # Update fuel-agent in MCollective
        cmd = "rpm -q fuel-agent"
        old_package = \
            environment.base_actions.execute_in_container(
                cmd, container, exit_code=0)
        logger.info("Delete package {0}"
                    .format(old_package))

        cmd = "rpm -e fuel-agent"
        environment.base_actions.execute_in_container(
            cmd, container, exit_code=0)

        cmd = "ls -1 {0}|grep 'fuel-agent'".format(pack_path)
        new_package = \
            environment.base_actions.execute_in_container(
                cmd, container).rstrip('.rpm')
        logger.info("Install package {0}"
                    .format(new_package))

        cmd = "yum localinstall -y {0}fuel-agent*.rpm".format(
            pack_path)
        environment.base_actions.execute_in_container(
            cmd, container, exit_code=0)

        cmd = "rpm -q fuel-agent"
        installed_package = \
            environment.base_actions.execute_in_container(
                cmd, container, exit_code=0)

        assert_equal(installed_package, new_package,
                     "The new package {0} was not installed".
                     format(new_package))
    except Exception as e:
        logger.error("Could not upload package {e}".format(e=e))
        raise


def patch_bootstrap(environment):
    """Replaced initramfs.img in /var/www/nailgun/
    with newly_builded from review
    environment - Environment Model object - self.env
    """
    logger.info("Update fuel-agent code and assemble new bootstrap")
    if not settings.UPDATE_FUEL:
        raise Exception("{} variable don't exist"
                        .format(settings.UPDATE_FUEL))
    try:
        pack_path = '/var/www/nailgun/fuel-agent-review/'
        with environment.d_env.get_admin_remote() as remote:
            remote.upload(settings.UPDATE_FUEL_PATH.rstrip('/'),
                          pack_path)
            # renew code in bootstrap

            # Step 1 - unpack bootstrap
            bootstrap_var = "/var/initramfs"
            bootstrap = "/var/www/nailgun/bootstrap"
            cmd = ("mkdir {0};"
                   "cp /{1}/initramfs.img {0}/;"
                   "cd {0};"
                   "cat initramfs.img | gunzip | cpio -imudv;").format(
                bootstrap_var,
                bootstrap
            )
            with environment.d_env.get_admin_remote() as remote:
                result = remote.execute(cmd)
                assert_equal(result['exit_code'], 0,
                             ('Failed to add unpack bootstrap {}'
                              ).format(result))

            # Step 2 - replace fuel-agent code in unpacked bootstrap
            agent_path = "/usr/lib/python2.6/site-packages/fuel_agent"
            image_rebuild = "{} | {} | {}".format(
                "find . -xdev",
                "cpio --create --format='newc'",
                "gzip -9 > /var/initramfs/initramfs.img.updated")

            cmd = ("rm -rf {0}{1}/*;"
                   "rm -rf {0}/initramfs.img"
                   "cp -r {2}fuel-agent/fuel_agent/* {0}{1}/;"
                   "cd {0}/;"
                   "{3};"
                   ).format(
                bootstrap_var,
                agent_path,
                pack_path,
                image_rebuild)

            with environment.d_env.get_admin_remote() as remote:
                result = remote.execute(cmd)
                assert_equal(result['exit_code'], 0,
                             ('Failed to add rebuild bootstrap {}'
                              ).format(result))
    except Exception as e:
        logger.error("Could not upload package {e}".format(e=e))
        raise


def replace_bootstrap(environment):
    """Replaced initramfs.img in /var/www/nailgun/
    with re-builded with review code
    environment - Environment Model object - self.env
    """
    logger.info("Updating bootstrap")
    if not settings.UPDATE_FUEL:
        raise Exception("{} variable don't exist"
                        .format(settings.UPDATE_FUEL))
    try:
        rebuilded_bootstrap = '/var/initramfs/'
        logger.info("Assigning new bootstrap from {}"
                    .format(rebuilded_bootstrap))
        bootstrap = "/var/www/nailgun/bootstrap"
        cmd = ("rm {0}/initramfs.img;"
               "cp {1}/initramfs.img.updated {0}/initramfs.img;"
               "chmod +r {0}/initramfs.img;"
               ).format(bootstrap, rebuilded_bootstrap)
        with environment.d_env.get_admin_remote() as remote:
            checkers.check_file_exists(
                remote,
                '{0}initramfs.img.updated'.format(rebuilded_bootstrap))
            result = remote.execute(cmd)
            assert_equal(result['exit_code'], 0,
                         ('Failed to assign bootstrap {}'
                          ).format(result))
        cmd = "cobbler sync"
        container = "cobbler"
        environment.base_actions.execute_in_container(
            cmd, container, exit_code=0)
    except Exception as e:
        logger.error("Could not upload package {e}".format(e=e))
        raise
