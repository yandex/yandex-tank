from threading import Thread, Event

import requests
import time
import logging

logger = logging.getLogger(__name__)


class PandoraStatsPoller(Thread):
    def __init__(self):
        super(PandoraStatsPoller, self).__init__()
        self._stop = Event()
        self.buffer = []

    def run(self):
        last_ts = int(time.time() - 1)

        while not self._stop.is_set():
            curr_ts = int(time.time())
            if curr_ts > last_ts:
                last_ts = curr_ts
                try:
                    pandora_stat = requests.get("http://localhost:1234/debug/vars", timeout=0.9).json()
                    data = {
                        'ts': last_ts - 1,
                        'metrics': {
                            'instances': pandora_stat.get("engine_ActiveRequests"),
                            'reqps': pandora_stat.get("engine_ReqPS"),
                        }
                    }
                except (requests.ConnectionError, requests.HTTPError, requests.exceptions.Timeout):
                    logger.debug("Pandora expvar http interface is unavailable", exc_info=True)
                    data = {
                        'ts': last_ts - 1,
                        'metrics': {
                            'instances': 0,
                            'reqps': 0
                        }
                    }
                self.buffer.append(data)
            else:
                time.sleep(0.2)

    def stop(self):
        self._stop.set()

    def get_data(self):
        result, self.buffer = self.buffer, []
        return result


class PandoraStatsReader(object):
    # TODO: maybe make stats collection asyncronous
    def __init__(self, expvar):
        self.closed = False
        self.expvar = expvar
        self.poller = PandoraStatsPoller()
        self.started = False

    def next(self):
        if not self.expvar:
            if self.closed:
                raise StopIteration
            return [{
                'ts': int(time.time() - 1),
                'metrics': {
                    'instances': 0,
                    'reqps': 0
                }
            }]
        else:
            if self.closed:
                raise StopIteration()
            elif not self.started:
                self.poller.start()
                self.started = True
            return self.poller.get_data()

    def close(self):
        self.closed = True
        self.poller.stop()
        self.poller.join()

    def __iter__(self):
        return self
