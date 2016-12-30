import requests
import time
import logging

logger = logging.getLogger(__name__)


class PandoraStatsReader(object):
    # TODO: maybe make stats collection asyncronous

    def next(self):
        try:
            pandora_response = requests.get("http://localhost:1234/debug/vars")
            pandora_stat = pandora_response.json()

            return [{
                'ts': int(time.time() - 1),
                'metrics': {
                    'instances': pandora_stat.get("engine_ActiveRequests"),
                    'reqps': pandora_stat.get("engine_ReqPS"),
                }
            }]
        except requests.ConnectionError:
            logger.info("Pandora expvar http interface is unavailable")
        except requests.HTTPError:
            logger.warning(
                "Pandora expvar http interface is unavailable", exc_info=True)
        except Exception:
            logger.warning(
                "Couldn't decode pandora stat:\n%s\n",
                pandora_response.text,
                exc_info=True)

        return [{
            'ts': int(time.time() - 1),
            'metrics': {
                'instances': 0,
                'reqps': 0
            }
        }]

    def close(self):
        pass

    def __iter__(self):
        return self
