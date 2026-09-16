from threading import Thread, Event

import requests
import time
import logging

logger = logging.getLogger(__name__)


class PandoraStatsPoller(Thread):
    def __init__(self, port):
        super(PandoraStatsPoller, self).__init__()
        self._stop_run = Event()
        self._expvar_unavailable = False
        self.buffer = []
        self.port = port

    def _poll(self, timestamp):
        try:
            response = requests.get("http://localhost:{port}/debug/vars".format(port=self.port), timeout=0.9)
            response.raise_for_status()
            pandora_stat = response.json()
            if not isinstance(pandora_stat, dict) or pandora_stat.get("engine_ReqPS") is None:
                raise ValueError("Pandora expvar response does not contain engine_ReqPS")
            instances_metric = pandora_stat.get(
                "engine_LastMaxActiveRequests", pandora_stat.get("engine_ActiveRequests", 0)
            )
            data = {
                'ts': timestamp,
                'metrics': {
                    'instances': instances_metric,
                    'reqps': pandora_stat.get("engine_ReqPS"),
                },
            }
        except (requests.RequestException, TypeError, ValueError):
            if not self._expvar_unavailable:
                logger.warning(
                    "Pandora expvar http interface on port %s is unavailable; "
                    "sent RPS is unavailable and Tank will publish a zero fallback until recovery",
                    self.port,
                    exc_info=True,
                )
            self._expvar_unavailable = True
            return {'ts': timestamp, 'metrics': {'instances': 0, 'reqps': 0}}

        if self._expvar_unavailable:
            logger.info("Pandora expvar http interface on port %s is available again", self.port)
        self._expvar_unavailable = False
        return data

    def run(self):
        last_ts = int(time.time() - 1)

        while not self._stop_run.is_set():
            curr_ts = int(time.time())
            if curr_ts > last_ts:
                last_ts = curr_ts
                self.buffer.append(self._poll(last_ts - 1))
            else:
                time.sleep(0.2)

    def stop(self):
        self._stop_run.set()

    def get_data(self):
        result, self.buffer = self.buffer, []
        return result


class PandoraStatsReader(object):
    # TODO: maybe make stats collection asyncronous
    def __init__(self, expvar, port):
        self.closed = False
        self.expvar = expvar
        self.port = port
        self.poller = PandoraStatsPoller(port)
        self.started = False

    def __next__(self):
        if not self.expvar:
            if self.closed:
                raise StopIteration
            return [{'ts': int(time.time() - 1), 'metrics': {'instances': 0, 'reqps': 0}}]
        else:
            if self.closed:
                raise StopIteration()
            elif not self.started:
                self.poller.start()
                self.started = True
            return self.poller.get_data()

    def close(self):
        self.closed = True
        if self.poller.is_alive():
            self.poller.stop()
            self.poller.join()

    def __iter__(self):
        return self
