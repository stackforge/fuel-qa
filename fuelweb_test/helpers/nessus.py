import json
import urlparse

from devops.helpers.helpers import wait
from proboscis import asserts
import requests

from fuelweb_test import logger


class NessusClient(object):
    def __init__(self, hostname, port, username, password, ssl_verify=False):
        self.nessus_auth_token = None
        self.nessus_base_url = 'https://{0}:{1}'.format(hostname, port)
        self.nessus_username = username
        self.nessus_password = password
        self.ssl_verify = ssl_verify

    def request(self, method, url, body=None, **kwargs):
        if self.nessus_auth_token is None:
            self.login()

        headers = {'X-Cookie': 'token={0}'.format(self.nessus_auth_token),
                   'Content-Type': 'application/json'}
        url = urlparse.urljoin(self.nessus_base_url, url)

        logger.debug("Request {0} {1} \nHeaders: {2}\nBody: {3}"
                     .format(method, url, headers, body))

        response = requests.request(
            method, url, data=body, headers=headers,
            verify=self.ssl_verify, **kwargs)

        logger.debug("Response Status: {0} \nHeaders: {1}\nBody: {2}"
                     .format(response.status_code,
                             response.headers,
                             response.iter_content(10240)))

        asserts.assert_equal(
            response.status_code, 200,
            "Request failed: {0}\n{1}".format(response.status_code,
                                              response.json()))

        return response

    def get(self, url, body=None):
        return self.request("GET", url, json.dumps(body)).json()

    def get_raw(self, url, body=None):
        return self.request("GET", url, json.dumps(body)).content

    def post(self, url, body=None):
        return self.request("POST", url, json.dumps(body)).json()

    def login(self):
        creds = {'username': self.nessus_username,
                 'password': self.nessus_password}

        self.nessus_auth_token = self.post('/login', creds)['token']

    def add_policy(self, policy_def):
        return self.post('/policies', policy_def)

    def list_policy_templates(self):
        return self.get('/editor/policy/templates')

    def add_cpa_policy(self, name, description, pid):
        policy_def = \
            {
                "uuid": pid,
                "settings": {
                    "name": name,
                    "description": description
                },
                "credentials": {
                    "add": {
                        "Host": {
                            "SSH": [
                                {
                                    "auth_method": "password",
                                    "username": "root",
                                    "password": "r00tme",
                                    "elevate_privileges_with": "Nothing"
                                }
                            ]
                        }
                    }
                }
            }

        return self.add_policy(policy_def)['policy_id']

    def add_wat_policy(self, name, desc, pid):
        policy_def = \
            {
                "uuid": pid,
                "settings": {
                    "name": name,
                    "description": desc,
                    "discovery_mode": "Port scan (all ports)",
                    "assessment_mode": "Scan for all web vulnerabilities "
                                       "(complex)",

                }
            }

        return self.add_policy(policy_def)['policy_id']

    def create_scan(self, name, description, target_ip,
                    policy_id, policy_template_id):
        scan_def = \
            {
                "uuid": policy_template_id,
                "settings": {
                    "name": name,
                    "description": description,
                    "scanner_id": "1",
                    "policy_id": policy_id,
                    "text_targets": target_ip,
                    "launch": "ONETIME",
                    "enabled": False,
                    "launch_now": False
                }
            }

        return self.post('/scans', scan_def)['scan']['id']

    def launch_scan(self, scan_id):
        return self.post('/scans/{0}/launch'.format(scan_id))['scan_uuid']

    def get_scan_history(self, scan_id, history_id):
        return self.get('/scans/{0}'.format(scan_id),
                        {'history_id': history_id})['info']

    def get_scan_status(self, scan_id, history_id):
        return self.get_scan_history(scan_id, history_id)['status']

    def list_scan_history_ids(self, scan_id):
        data = self.get('/scans/{0}'.format(scan_id))
        return dict((h['uuid'], h['history_id']) for h in data['history'])

    def check_scan_export_status(self, scan_id, file_id):
        return self.get('/scans/{0}/export/{1}/status'
                        .format(scan_id, file_id))['status'] == 'ready'

    def export_scan(self, scan_id, history_id, save_format):
        export_def = {'history_id': history_id,
                      'format': save_format,
                      'chapters': 'vuln_hosts_summary'}
        file_id = self.post('/scans/{0}/export'.format(scan_id),
                            body=export_def)['file']
        wait(lambda: self.check_scan_export_status(scan_id, file_id),
             interval=10, timeout=600)
        return file_id

    def download_scan_result(self, scan_id, file_id, save_format):
        report = self.get_raw('/scans/{0}/export/{1}/download'
                              .format(scan_id, file_id))

        filename = 'nessus_report_{0}.{1}'.format(scan_id, save_format)
        logger.info("Saving Nessus scan report: {0}".format(filename))
        with open(filename, 'w') as report_file:
            report_file.write(report)
