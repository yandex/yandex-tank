import json
import time
import traceback
import urllib
from future.moves.urllib.parse import urljoin
from builtins import range

import requests
import logging

from requests.exceptions import ConnectionError, Timeout

requests.packages.urllib3.disable_warnings()
logger = logging.getLogger(__name__)  # pylint: disable=C0103


class APIClient(object):

    def __init__(
            self,
            base_url=None,
            writer_url=None,
            network_attempts=10,
            api_attempts=10,
            maintenance_attempts=40,
            network_timeout=2,
            api_timeout=5,
            maintenance_timeout=15,
            connection_timeout=5.0,
            user_agent=None,
            api_token=None):
        self.user_agent = user_agent
        self.connection_timeout = connection_timeout
        self._base_url = base_url
        self.writer_url = writer_url

        self.retry_timeout = 10
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"User-Agent": "tank"})

        self.network_attempts = network_attempts
        self.network_timeout = network_timeout
        self.api_attempts = api_attempts
        self.api_timeout = api_timeout
        self.maintenance_attempts = maintenance_attempts
        self.maintenance_timeout = maintenance_timeout
        self.params = {'api_token': api_token} if api_token else {}

    @property
    def base_url(self):
        if not self._base_url:
            raise ValueError("Base url is not set")
        else:
            return self._base_url

    @base_url.setter
    def base_url(self, url):
        self._base_url = url

    class UnderMaintenance(Exception):
        message = "API is under maintenance"

    class NotAvailable(Exception):
        desc = "API is not available"

        def __init__(self, request, response):
            self.message = "%s\n%s\n%s" % (self.desc, request, response)
            super(self.__class__, self).__init__(self.message)

    class StoppedFromOnline(Exception):
        message = "Shooting is stopped from online"

    class JobNotCreated(Exception):
        pass

    class NetworkError(Exception):
        pass

    def set_api_timeout(self, timeout):
        self.api_timeout = float(timeout)

    def network_timeouts(self):
        return (self.network_timeout for _ in range(self.network_attempts - 1))

    def api_timeouts(self):
        return (self.api_timeout for _ in range(self.api_attempts - 1))

    def maintenance_timeouts(self):
        return (
            self.maintenance_timeout for _ in range(
                self.maintenance_attempts - 1))

    @staticmethod
    def filter_headers(headers):
        boring = ['X-Content-Security-Policy', 'Content-Security-Policy',
                  'Strict-Transport-Security', 'X-WebKit-CSP', 'Set-Cookie',
                  'X-DNS-Prefetch-Control', 'X-Frame-Options', 'P3P',
                  'X-Content-Type-Options', 'X-Download-Options',
                  'Surrogate-Control']
        for h in boring:
            if h in headers:
                del (headers[h])
        return headers

    def __send_single_request(self, req, trace=False):
        p = self.session.prepare_request(req)
        if trace:
            logger.debug("Making request: %s %s Headers: %s Body: %s",
                         p.method, p.url, p.headers, p.body)
        resp = self.session.send(p, timeout=self.connection_timeout)
        if trace:
            logger.debug("Got response in %ss: %s %s Headers: %s Body: %s",
                         resp.elapsed.total_seconds(), resp.reason,
                         resp.status_code, self.filter_headers(resp.headers),
                         resp.content)
        if resp.status_code in [500, 502, 503, 504]:
            raise self.NotAvailable(
                request="request: %s %s\n\tHeaders: %s\n\tBody: %s" %
                (p.method,
                 p.url,
                 p.headers,
                 p.body),
                response="Got response in %ss: %s %s\n\tHeaders: %s\n\tBody: %s" %
                (resp.elapsed.total_seconds(),
                 resp.reason,
                 resp.status_code,
                 self.filter_headers(
                    resp.headers),
                    resp.content))
        elif resp.status_code == 410:
            raise self.StoppedFromOnline
        elif resp.status_code == 423:
            raise self.UnderMaintenance
        else:
            resp.raise_for_status()
            return resp

    def __make_api_request(
            self,
            http_method,
            path,
            data=None,
            response_callback=lambda x: x,
            writer=False,
            trace=False,
            json=None,
            maintenance_timeouts=None,
            maintenance_msg=None):
        url = urljoin(self.base_url, path)
        if json:
            request = requests.Request(
                http_method, url, json=json, headers={'User-Agent': self.user_agent}, params=self.params)
        else:
            request = requests.Request(
                http_method, url, data=data, headers={'User-Agent': self.user_agent}, params=self.params)
        network_timeouts = self.network_timeouts()
        maintenance_timeouts = maintenance_timeouts or self.maintenance_timeouts()
        maintenance_msg = maintenance_msg or "%s is under maintenance" % (self._base_url)
        while True:
            try:
                response = self.__send_single_request(request, trace=trace)
                return response_callback(response)
            except (Timeout, ConnectionError):
                logger.warn(traceback.format_exc())
                try:
                    timeout = next(network_timeouts)
                    logger.warn(
                        "Network error, will retry in %ss..." %
                        timeout)
                    time.sleep(timeout)
                    continue
                except StopIteration:
                    raise self.NetworkError()
            except self.UnderMaintenance as e:
                try:
                    timeout = next(maintenance_timeouts)
                    logger.warn(maintenance_msg)
                    logger.warn("Retrying in %ss..." % timeout)
                    time.sleep(timeout)
                    continue
                except StopIteration:
                    raise e

    def __make_writer_request(
            self,
            params=None,
            json=None,
            http_method="POST",
            trace=False):
        '''
        Send request to writer service.
        '''
        request = requests.Request(
            http_method,
            self.writer_url,
            params=params,
            json=json,
            headers={
                'User-Agent': self.user_agent})
        network_timeouts = self.network_timeouts()
        maintenance_timeouts = self.maintenance_timeouts()
        while True:
            try:
                response = self.__send_single_request(request, trace=trace)
                return response
            except (Timeout, ConnectionError):
                logger.warn(traceback.format_exc())
                try:
                    timeout = next(network_timeouts)
                    logger.warn(
                        "Network error, will retry in %ss..." %
                        timeout)
                    time.sleep(timeout)
                    continue
                except StopIteration:
                    raise self.NetworkError()
            except self.UnderMaintenance as e:
                try:
                    timeout = next(maintenance_timeouts)
                    logger.warn(
                        "Writer is under maintenance, will retry in %ss..." %
                        timeout)
                    time.sleep(timeout)
                    continue
                except StopIteration:
                    raise e

    def __get(self, addr, trace=False, maintenance_timeouts=None, maintenance_msg=None):
        return self.__make_api_request(
            'GET',
            addr,
            trace=trace,
            response_callback=lambda r: json.loads(r.content.decode('utf8')),
            maintenance_timeouts=maintenance_timeouts,
            maintenance_msg=maintenance_msg
        )

    def __post_raw(self, addr, txt_data, trace=False):
        return self.__make_api_request(
            'POST', addr, txt_data, lambda r: r.content, trace=trace)

    def __post(self, addr, data, trace=False):
        return self.__make_api_request(
            'POST',
            addr,
            json=data,
            response_callback=lambda r: r.json(),
            trace=trace)

    def __put(self, addr, data, trace=False):
        return self.__make_api_request(
            'PUT',
            addr,
            json=data,
            response_callback=lambda r: r.text,
            trace=trace)

    def __patch(self, addr, data, trace=False):
        return self.__make_api_request(
            'PATCH',
            addr,
            json=data,
            response_callback=lambda r: r.text,
            trace=trace)

    def get_task_data(self, task, trace=False):
        return self.__get("api/task/" + task + "/summary.json", trace=trace)

    def new_job(
            self,
            task,
            person,
            tank,
            target_host,
            target_port,
            loadscheme=None,
            detailed_time=None,
            notify_list=None,
            trace=False):
        """
        :return: job_nr, upload_token
        :rtype: tuple
        """
        if not notify_list:
            notify_list = []
        data = {
            'task': task,
            'person': person,
            'tank': tank,
            'host': target_host,
            'port': target_port,
            'loadscheme': loadscheme,
            'detailed_time': detailed_time,
            'notify': notify_list
        }

        logger.debug("Job create request: %s", data)
        api_timeouts = self.api_timeouts()
        while True:
            try:
                response = self.__post(
                    "api/job/create.json", data, trace=trace)[0]
                # [{"upload_token": "1864a3b2547d40f19b5012eb038be6f6", "job": 904317}]
                return response['job'], response['upload_token']
            except (self.NotAvailable, self.StoppedFromOnline) as e:
                try:
                    timeout = next(api_timeouts)
                    logger.warn("API error, will retry in %ss..." % timeout)
                    time.sleep(timeout)
                    continue
                except StopIteration:
                    logger.warn('Failed to create job on lunapark')
                    raise self.JobNotCreated(e.message)
            except requests.HTTPError as e:
                raise self.JobNotCreated('Failed to create job on lunapark\n{}'.format(e.response.content))
            except Exception as e:
                logger.warn('Failed to create job on lunapark')
                logger.warn(e.message)
                raise self.JobNotCreated()

    def get_job_summary(self, jobno):
        result = self.__get('api/job/' + str(jobno) + '/summary.json')
        return result[0]

    def close_job(self, jobno, retcode, trace=False):
        params = {'exitcode': str(retcode)}

        result = self.__get('api/job/' + str(jobno) + '/close.json?' +
                            urllib.urlencode(params), trace=trace)
        return result[0]['success']

    def edit_job_metainfo(
            self,
            jobno,
            job_name,
            job_dsc,
            instances,
            ammo_path,
            loop_count,
            version_tested,
            is_regression,
            component,
            cmdline,
            is_starred,
            tank_type=0,
            trace=False):
        data = {
            'name': job_name,
            'description': job_dsc,
            'instances': str(instances),
            'ammo': ammo_path,
            'loop': loop_count,
            'version': version_tested,
            'regression': str(is_regression),
            'component': component,
            'tank_type': int(tank_type),
            'command_line': cmdline,
            'starred': int(is_starred)
        }

        response = self.__post(
            'api/job/' +
            str(jobno) +
            '/edit.json',
            data,
            trace=trace)
        return response

    def set_imbalance_and_dsc(self, jobno, rps, comment):
        data = {}
        if rps:
            data['imbalance'] = rps
        if comment:
            res = self.get_job_summary(jobno)
            data['description'] = (res['dsc'] + "\n" + comment).strip()

        response = self.__post('api/job/' + str(jobno) + '/edit.json', data)
        return response

    def second_data_to_push_item(self, data, stat, timestamp, overall, case):
        """
        @data: SecondAggregateDataItem
        """
        api_data = {
            'overall': overall,
            'case': case,
            'net_codes': [],
            'http_codes': [],
            'time_intervals': [],
            'trail': {
                'time': str(timestamp),
                'reqps': stat["metrics"]["reqps"],
                'resps': data["interval_real"]["len"],
                'expect': data["interval_real"]["total"] / 1000.0 /
                data["interval_real"]["len"],
                'disper': 0,
                'self_load':
                    0,  # TODO abs(round(100 - float(data.selfload), 2)),
                'input': data["size_in"]["total"],
                'output': data["size_out"]["total"],
                'connect_time': data["connect_time"]["total"] / 1000.0 /
                data["connect_time"]["len"],
                'send_time':
                    data["send_time"]["total"] / \
                1000.0 / data["send_time"]["len"],
                'latency':
                    data["latency"]["total"] / 1000.0 / data["latency"]["len"],
                'receive_time': data["receive_time"]["total"] / 1000.0 /
                data["receive_time"]["len"],
                'threads': stat["metrics"]["instances"],  # TODO
            }
        }

        for q, value in zip(data["interval_real"]["q"]["q"],
                            data["interval_real"]["q"]["value"]):
            api_data['trail']['q' + str(q)] = value / 1000.0

        for code, cnt in data["net_code"]["count"].items():
            api_data['net_codes'].append({'code': int(code),
                                          'count': int(cnt)})

        for code, cnt in data["proto_code"]["count"].items():
            api_data['http_codes'].append({'code': int(code),
                                           'count': int(cnt)})

        api_data['time_intervals'] = self.convert_hist(data["interval_real"][
            "hist"])
        return api_data

    def convert_hist(self, hist):
        data = hist['data']
        bins = hist['bins']
        return [
            {
                "from": 0,  # deprecated
                "to": b / 1000.0,
                "count": count,
            } for b, count in zip(bins, data)
        ]

    def push_test_data(
            self,
            jobno,
            upload_token,
            data_item,
            stat_item,
            trace=False):
        items = []
        uri = 'api/job/{0}/push_data.json?upload_token={1}'.format(
            jobno, upload_token)
        ts = data_item["ts"]
        for case_name, case_data in data_item["tagged"].items():
            if case_name == "":
                case_name = "__NOTAG__"
            if (len(case_name)) > 128:
                raise RuntimeError('tag (case) name is too long: ' + case_name)
            push_item = self.second_data_to_push_item(case_data, stat_item, ts,
                                                      0, case_name)
            items.append(push_item)
        overall = self.second_data_to_push_item(data_item["overall"],
                                                stat_item, ts, 1, '')
        items.append(overall)

        api_timeouts = self.api_timeouts()
        while True:
            try:
                if self.writer_url:
                    res = self.__make_writer_request(
                        params={
                            "jobno": jobno,
                            "upload_token": upload_token,
                        },
                        json={
                            "trail": items,
                        },
                        trace=trace)
                    logger.debug("Writer response: %s", res.text)
                    return res.json()["success"]
                else:
                    res = self.__post(uri, items, trace=trace)
                    logger.debug("API response: %s", res)
                    success = int(res[0]['success'])
                    return success
            except self.NotAvailable as e:
                try:
                    timeout = next(api_timeouts)
                    logger.warn("API error, will retry in %ss...", timeout)
                    time.sleep(timeout)
                    continue
                except StopIteration:
                    raise e

    def push_monitoring_data(
            self,
            jobno,
            upload_token,
            send_data,
            trace=False):
        if send_data:
            addr = "api/monitoring/receiver/push?job_id=%s&upload_token=%s" % (
                jobno, upload_token)
            api_timeouts = self.api_timeouts()
            while True:
                try:
                    if self.writer_url:
                        res = self.__make_writer_request(
                            params={
                                "jobno": jobno,
                                "upload_token": upload_token,
                            },
                            json={
                                "monitoring": send_data,
                            },
                            trace=trace)
                        logger.debug("Writer response: %s", res.text)
                        return res.json()["success"]
                    else:
                        res = self.__post_raw(
                            addr, json.dumps(send_data), trace=trace)
                        logger.debug("API response: %s", res)
                        success = res == 'ok'
                        return success
                except self.NotAvailable as e:
                    try:
                        timeout = next(api_timeouts)
                        logger.warn("API error, will retry in %ss...", timeout)
                        time.sleep(timeout)
                        continue
                    except StopIteration:
                        raise e

    def send_status(self, jobno, upload_token, status, trace=False):
        addr = "api/v2/jobs/%s/?upload_token=%s" % (jobno, upload_token)
        status_line = status.get("core", {}).get("stage", "unknown")
        if "stepper" in status:
            status_line += " %s" % status["stepper"].get("progress")
        api_timeouts = self.api_timeouts()
        while True:
            try:
                self.__patch(addr, {"status": status_line}, trace=trace)
                return
            except self.NotAvailable as e:
                try:
                    timeout = next(api_timeouts)
                    logger.warn("API error, will retry in %ss...", timeout)
                    time.sleep(timeout)
                    continue
                except StopIteration:
                    raise e

    def is_target_locked(self, target, trace=False):
        addr = "api/server/lock.json?action=check&address=%s" % target
        res = self.__get(addr, trace=trace)
        return res[0]

    def lock_target(self, target, duration, trace=False, maintenance_timeouts=None, maintenance_msg=None):
        addr = "api/server/lock.json?action=lock&" + \
               "address=%s&duration=%s&jobno=None" % \
               (target, int(duration))
        res = self.__get(addr, trace=trace, maintenance_timeouts=maintenance_timeouts, maintenance_msg=maintenance_msg)
        return res[0]

    def unlock_target(self, target):
        addr = self.get_manual_unlock_link(target)
        res = self.__get(addr)
        return res[0]

    def get_virtual_host_info(self, hostname):
        addr = "api/server/virtual_host.json?hostname=%s" % hostname
        res = self.__get(addr)
        try:
            return res[0]
        except KeyError:
            raise Exception(res['error'])

    @staticmethod
    def get_manual_unlock_link(target):
        return "api/server/lock.json?action=unlock&address=%s" % target

    def send_config_snapshot(self, jobno, config, trace=False):
        logger.debug("Sending config snapshot")
        addr = "api/job/%s/configinfo.txt" % jobno
        self.__post_raw(addr, {"configinfo": config}, trace=trace)


class OverloadClient(APIClient):

    def send_status(self, jobno, upload_token, status, trace=False):
        return

    def lock_target(self, target, duration, trace=False, **kwargs):
        return

    def unlock_target(self, *args, **kwargs):
        return
