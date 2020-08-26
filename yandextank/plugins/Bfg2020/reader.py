from threading import Thread, Event
import requests
import time
import logging
logger = logging.getLogger(__name__)


class BfgStatsPoller(Thread):
    def __init__(self, port):
        super(BfgStatsPoller, self).__init__()
        self.stopped = Event()
        self.buffer = []
        self.port = port

    def run(self):
        last_ts = int(time.time() - 1)
        while not self.stopped.is_set():
            curr_ts = int(time.time())
            if curr_ts > last_ts:
                last_ts = curr_ts
                try:
                    bfg_stat = requests.get(
                        "http://localhost:{port}/stats".format(port=self.port), timeout=0.9
                    ).json()
                    data = {
                        'ts': last_ts - 1,
                        'metrics': {
                            'instances': bfg_stat.get('instances'),
                            'reqps': bfg_stat.get('reqps')
                        }
                    }
                except (requests.ConnectionError, requests.HTTPError, requests.exceptions.Timeout):
                    logger.debug("Bfg http stat server interface is unavailable", exc_info=True)
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
        self.stopped.set()

    def get_data(self):
        result, self.buffer = self.buffer, []
        return result


class BfgStatsReader(object):
    def __init__(self, port):
        self.closed = False
        self.port = port
        self.poller = BfgStatsPoller(port)
        self.started = False

    def __next__(self):
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
