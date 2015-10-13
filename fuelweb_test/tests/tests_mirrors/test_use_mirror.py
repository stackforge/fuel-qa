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

from proboscis import test

from fuelweb_test.settings import DEPLOYMENT_MODE
from fuelweb_test.settings import NEUTRON_SEGMENT
from fuelweb_test.tests.base_test_case import SetupEnvironment
from fuelweb_test.tests.base_test_case import TestBasic


@test(groups=['fuel-mirror'])
class TestUseMirror(TestBasic):
    """In this test we use created mirrors to deploy environment.

    This test not only tests create mirror utility but also state of our
    mirrors.
    Install packetary
    """

    @test(groups=['fuel-mirror', 'use-mirror'],
          depends_on=[SetupEnvironment.prepare_slaves_5],)  # robustness, etc?
    def deploy_with_custom_mirror(self):
        """Deploy it!

        Scenario:
            1. Install packetary
            2. Create mirror
            3. Create cluster
            4. Add 3 nodes with controller role
            5. Add 1 node with compute role and 1 node with cinder role
            6. Run network verification
            7. Deploy the cluster
            8. Run OSTF

        Duration 30m
        Snapshot deploy_with_custom_mirror
        """
        self.env.revert_snapshot('ready_with_5_slaves')

        self.show_step(1)
        # cd /tmp
        # yum install git python-lxml.x86_64
        # pip install -e git+https://github.com/bgaifullin/packetary.git#egg=Package
        # packetary mirror -o "http://archive.ubuntu.com/ubuntu/ trusty main universe multiverse restricted" -r "http://10.109.5.2:8080/2015.1.0-7.0/ubuntu/x86_64 mos7.0 main restricted" -d /var/www/nailgun/mirror/ubuntu_required -b ubuntu-minimal ldconfig libapt-inst libc-bin dash  multiarch-support  gcc-4.9-base apt apt-utils bash console-setup cron debconf-i18n diffutils e2fslibs eject gnupg gpgv grep gzip hostname iputils-ping isc-dhcp-client isc-dhcp-common kbd keyboard-configuration less libapt-inst1.5 libapt-pkg4.12 libarchive-extract-perl  libestr0 libc-bin libcap2-bin libfribidi0 libgnutls-openssl27 liblocale-gettext-perl liblockfile-bin liblockfile1 liblog-message-simple-perl libmodule-pluggable-perl libmount1 libnewt0.52 libpam-cap libpam-modules-bin libpod-latex-perl libpam-runtime libslang2 libss2 libterm-ui-perl libtext-charwidth-perl libtext-iconv-perl libtext-soundex-perl libtext-wrapi18n-perl libusb-0.1-4 locales lockfile-progs  login logrotate lsb-release mawk multiarch-support ncurses-base ncurses-bin net-tools netbase ntpdate resolvconf rsyslog  sed sudo tar ubuntu-keyring ucf ureadahead vim-common vim-tiny whiptail xkb-data acl anacron build-essential debconf-utils ruby-augeas ruby-ipaddress ruby-shadow ruby-stomp telnet ubuntu-standard vim virt-what vlan ruby-ipaddress acl anacron bash-completion bridge-utils bsdmainutils build-essential cloud-init curl daemonize debconf-utils gdisk grub-pc i40e-dkms linux-firmware linux-firmware-nonfree linux-headers-generic-lts-trusty linux-image-generic-lts-trusty lvm2 mcollective mdadm nailgun-agent nailgun-mcagents nailgun-net-check ntp openssh-client openssh-server puppet python-amqp ruby-augeas ruby-ipaddress ruby-json ruby-netaddr ruby-openstack ruby-shadow ruby-stomp telnet ubuntu-minimal ubuntu-standard uuid-runtime vim virt-what vlan puppetmaster-common facter "ohai lt 7" python-scapy cliff-tablib python-keystoneclient python-neutronclient python-pypcap
        # deb [arch=amd64] http://10.109.5.2:8080/ubuntu_required/ mos8.0 main
        # deb http://10.109.5.2:8080/mirror/ubuntu_required/ trusty main universe multiverse
        # scp root@10.109.5.2:/var/log/docker-logs/fuel-agent-env-1.log ~/Downloads
        # 2015-10-21 \d*:\d*:\d*.\d* \d*
        """cat ubuntu_required/dists/trusty/Release
Origin: Ubuntu
Label: Ubuntu
Suite: trusty
Version: 14.04
Codename: trusty
Date: Thu, 08 May 2014 14:19:09 UTC
Architectures: amd64 arm64 armhf i386 powerpc ppc64el
Components: main restricted universe multiverse
Description: Ubuntu Trusty 14.04
MD5Sum:
 cd299c6a3e6369807baac0b4c051e79a          94270 main/binary-amd64/Packages.gz
 a703b328d47bbd900a7b272f52be1b48         414873 main/binary-amd64/Packages
SHA1:
 9104fc743430ef36a79b869618e68eb0861aad0d          414873 main/binary-amd64/Packages
SHA256:
 508354056cf82690bab89bf89a66cacd7776d3e06e746856742a9fd801bf11e9          414873 main/binary-amd64/Packages
"""

        self.show_step(2)

        """ START Run packetary
        logger.info("Executing 'fuel-createmirror' on Fuel admin node")
        with self.env.d_env.get_admin_remote() as remote:
            if OPENSTACK_RELEASE_UBUNTU in OPENSTACK_RELEASE:
                cmd = ("sed -i 's/DEBUG=\"no\"/DEBUG=\"yes\"/' {}"
                       .format('/etc/fuel-createmirror/ubuntu.cfg'))
                remote.execute(cmd)
            else:
                pass
            result = remote.execute('fuel-createmirror')
        # END Run packetary"""

        """ START Check if there all repos were replaced with local mirrors
        ubuntu_id = self.fuel_web.client.get_release_id(
            release_name=OPENSTACK_RELEASE_UBUNTU)
        ubuntu_release = self.fuel_web.client.get_release(ubuntu_id)
        ubuntu_meta = ubuntu_release['attributes_metadata']
        repos_ubuntu = ubuntu_meta['editable']['repo_setup']["repos"]['value']
        remote_repos = []
        for repo_value in repos_ubuntu:
            if (self.fuel_web.admin_node_ip not in repo_value['uri'] and
                    '{settings.MASTER_IP}' not in repo_value['uri']):
                remote_repos.append({repo_value['name']: repo_value['uri']})
        assert_true(not remote_repos,
                    "Some repositories weren't replaced with local mirrors: "
                    "{0}".format(remote_repos))
        # END Check if there all repos were replaced with local mirrors"""

        """cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                'net_provider': 'neutron',

                'sahara': True,
                'murano': True,
                'ceilometer': True,
                'volumes_lvm': True,
                'volumes_ceph': False,
                'images_ceph': True,
                'osd_pool_size': "3"
            }
        )
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller', 'ceph-osd'],
                'slave-02': ['compute', 'ceph-osd'],
                'slave-03': ['cinder', 'ceph-osd'],
                'slave-04': ['mongo'],
                'slave-05': ['mongo']
            }
        )

        repos_attr = self.get_cluster_repos(cluster_id)
        self.fuel_web.report_repos(repos_attr)
        self.fuel_web.deploy_cluster_wait(cluster_id)"""

        self.show_step(3)
        cluster_id = self.fuel_web.create_cluster(
            name=self.__class__.__name__,
            mode=DEPLOYMENT_MODE,
            settings={
                "net_provider": 'neutron',
                "net_segment_type": NEUTRON_SEGMENT['tun'],
                'tenant': 'haTun',
                'user': 'haTun',
                'password': 'haTun'
            }
        )
        self.show_step(4)
        self.show_step(5)
        self.fuel_web.update_nodes(
            cluster_id,
            {
                'slave-01': ['controller'],
                'slave-02': ['controller'],
                'slave-03': ['controller'],
                'slave-04': ['compute'],
                'slave-05': ['cinder']
            }
        )
        self.show_step(6)
        self.fuel_web.verify_network(cluster_id)
        self.show_step(7)
        self.fuel_web.deploy_cluster_wait(cluster_id)

        self.show_step(8)
        self.fuel_web.run_ostf(
            cluster_id=cluster_id,
            test_sets=['ha', 'smoke', 'sanity'])

        self.env.make_snapshot('deploy_with_custom_mirror')
