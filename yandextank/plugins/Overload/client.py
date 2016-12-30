import datetime
import json
import time
import urllib
import requests
import logging

requests.packages.urllib3.disable_warnings()
logger = logging.getLogger(__name__)  # pylint: disable=C0103


class OverloadClient(object):
    def __init__(self):
        self.address = None
        self.token = None
        self.upload_token = ''
        self.api_token = ""
        self.api_timeout = None
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"User-Agent": "tank"})

    def set_api_address(self, addr):
        self.address = addr

    def set_api_timeout(self, timeout):
        self.api_timeout = float(timeout)

    def set_api_token(self, api_token):
        self.api_token = api_token

    def get_raw(self, addr):
        if not self.address:
            raise ValueError("Can't request unknown address")

        addr = self.address + addr
        logger.debug("Making request to: %s", addr)
        req = requests.Request('GET', addr)
        prepared = self.session.prepare_request(req)
        resp = self.session.send(prepared, timeout=self.api_timeout)
        resp.raise_for_status()
        resp_data = resp.content.strip()
        logger.debug("Raw response: %s", resp_data)
        return resp_data

    def get(self, addr):
        resp = self.get_raw(addr)
        response = json.loads(resp)
        logger.debug("Response: %s", response)
        return response

    def post_raw(self, addr, txt_data):
        if not self.address:
            raise ValueError("Can't request unknown address")

        addr = self.address + addr
        logger.debug("Making POST request to: %s", addr)
        req = requests.Request("POST", addr, data=txt_data)
        prepared = self.session.prepare_request(req)
        resp = self.session.send(prepared, timeout=self.api_timeout)
        resp.raise_for_status()
        logger.debug("Response: %s", resp.content)
        return resp.content

    def post(self, addr, data):
        addr = self.address + addr
        json_data = json.dumps(data, indent=2)
        logger.debug("Making POST request to: %s\n%s", addr, json_data)
        req = requests.Request("POST", addr, data=json_data)
        prepared = self.session.prepare_request(req)
        resp = self.session.send(prepared, timeout=self.api_timeout)
        resp.raise_for_status()
        logger.debug("Response: %s", resp.content)
        return resp.json()

    def get_task_data(self, task):
        return self.get("api/task/" + task + "/summary.json")

    def new_job(
            self, task, person, tank, target_host, target_port, loadscheme,
            detailed_time, notify_list):
        data = {
            'task': task,
            'person': person,
            'tank': tank,
            'host': target_host,
            'port': target_port,
            'loadscheme': loadscheme,
            'detailed_time': detailed_time,
            'notify': notify_list,
        }

        logger.debug("Job create request: %s", data)
        while True:
            try:
                response = self.post(
                    "api/job/create.json?api_token=" + self.api_token, data)
                self.upload_token = response[0].get('upload_token', '')
                return response[0]['job']
            except requests.exceptions.HTTPError as ex:
                logger.debug("Got error for job create request: %s", ex)
                if ex.response.status_code == 423:
                    logger.warn(
                        "Overload is under maintenance, will retry in 5s...")
                    time.sleep(5)
                else:
                    raise ex

        raise RuntimeError("Unreachable point hit")

    def get_job_summary(self, jobno):
        result = self.get(
            'api/job/' + str(jobno) + "/summary.json?api_token=" +
            self.api_token)
        return result[0]

    def close_job(self, jobno, retcode):
        params = {
            'exitcode': str(retcode),
            'api_token': self.api_token,
        }

        result = self.get(
            'api/job/' + str(jobno) + '/close.json?' + urllib.urlencode(params))
        return result[0]['success']

    def edit_job_metainfo(
            self, jobno, job_name, job_dsc, instances, ammo_path, loop_count,
            version_tested, is_regression, component, tank_type, cmdline,
            is_starred):
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
            'starred': int(is_starred),
        }

        response = self.post(
            'api/job/' + str(jobno) + "/edit.json?api_token=" + self.api_token,
            data)
        return response

    def set_imbalance_and_dsc(self, jobno, rps, comment):
        data = {}
        if rps:
            data['imbalance'] = rps
        if comment:
            data['description'] = comment.strip()

        response = self.post(
            'api/job/' + str(jobno) + "/set_imbalance.json?api_token=" +
            self.api_token, data)
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
                data["send_time"]["total"] / 1000.0 / data["send_time"]["len"],
                'latency':
                data["latency"]["total"] / 1000.0 / data["latency"]["len"],
                'receive_time': data["receive_time"]["total"] / 1000.0 /
                data["receive_time"]["len"],
                'threads': stat["metrics"]["instances"],  # TODO
            }
        }

        for q, value in zip(
                data["interval_real"]["q"]["q"],
                data["interval_real"]["q"]["value"]):
            api_data['trail']['q' + str(q)] = value / 1000.0

        for code, cnt in data["net_code"]["count"].iteritems():
            api_data['net_codes'].append({'code': int(code), 'count': int(cnt)})

        for code, cnt in data["proto_code"]["count"].iteritems():
            api_data['http_codes'].append({
                'code': int(code),
                'count': int(cnt)
            })

        api_data['time_intervals'] = self.convert_hist(
            data["interval_real"]["hist"])
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

    def push_test_data(self, jobno, data_item, stat_item):
        items = []
        uri = 'api/job/{0}/push_data.json?upload_token={1}'.format(
            jobno, self.upload_token)
        ts = datetime.datetime.fromtimestamp(data_item["ts"])
        for case_name, case_data in data_item["tagged"].iteritems():
            if case_name == "":
                case_name = "__EMPTY__"
            if (len(case_name)) > 128:
                raise RuntimeError('tag (case) name is too long: ' + case_name)
            push_item = self.second_data_to_push_item(
                case_data, stat_item, ts, 0, case_name)
            items.append(push_item)
        overall = self.second_data_to_push_item(
            data_item["overall"], stat_item, ts, 1, '')
        items.append(overall)

        while True:
            try:
                res = self.post(uri, items)
                break
            except requests.exceptions.HTTPError as ex:
                if ex.response.status_code == 400:
                    logger.error('Bad request to %s: %s', uri, ex)
                    return 0
                elif ex.response.status_code == 410:
                    logger.info("Test has been stopped by Overload server")
                    return 1
                else:
                    logger.warn(
                        "Unknown HTTP error while sending second data. "
                        "Retry in 10 sec: %s", ex)
                    time.sleep(10)  # FIXME this makes all plugins freeze
            except requests.exceptions.RequestException as ex:
                logger.warn(
                    "Failed to push second data to API,"
                    " retry in 10 sec: %s", ex)
                time.sleep(10)  # FIXME this makes all plugins freeze
            except Exception:  # pylint: disable=W0703
                # something nasty happened, but we don't want to fail here
                logger.exception(
                    "Unknown exception while pushing second data to API")
                return 0
        try:
            success = int(res[0]['success'])
        except Exception:  # pylint: disable=W0703
            logger.warning("Malformed response from API: %s", res)
            success = 0
        return success

    def push_monitoring_data(self, jobno, send_data):
        if send_data:
            addr = "api/monitoring/receiver/push?job_id=%s&upload_token=%s" % (
                jobno, self.upload_token)
            while True:
                try:
                    self.post_raw(addr, send_data)
                    return
                except requests.exceptions.HTTPError as ex:
                    if ex.response.status_code == 400:
                        logger.error('Bad request to %s: %s', addr, ex)
                        break
                    elif ex.response.status_code == 410:
                        logger.info("Test has been stopped by Overload server")
                        return
                    else:
                        logger.warning(
                            'Unknown http code while sending monitoring data,'
                            ' retry in 10s: %s', ex)
                        time.sleep(10)  # FIXME this makes all plugins freeze
                except requests.exceptions.RequestException as ex:
                    logger.warning(
                        'Problems sending monitoring data,'
                        ' retry in 10s: %s', ex)
                    time.sleep(10)  # FIXME this makes all plugins freeze
                except Exception:  # pylint: disable=W0703
                    # something irrecoverable happened
                    logger.exception(
                        "Unknown exception while pushing monitoring data to API")
                    return

    def send_console(self, jobno, console):
        logger.debug(
            "Sending console view [%s]: %s", len(console), console[:64])
        addr = ("api/job/%s/console.txt?api_token=" % jobno) + self.api_token,
        self.post_raw(addr, {"console": console, })

    def send_config_snapshot(self, jobno, config):
        logger.debug("Sending config snapshot")
        addr = ("api/job/%s/configinfo.txt?api_token=" % jobno) + self.api_token
        self.post_raw(addr, {"configinfo": config, })
