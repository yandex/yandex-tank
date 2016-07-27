"""
Monitoring stdout pipe reader. Read chunks from stdout and produce data frames
"""
import logging
import Queue
import json

from ..Telegraf.decoder import decoder


logger = logging.getLogger(__name__)

class MonitoringReader(object):
    def __init__(self, source):
        self.buffer = []
        self.source = source
        self.finished = False
        self.prev_check = None

    def __iter__(self):
        while not self.finished:
            try:
                yield self._decode_agents_data(self.source.get_nowait())
            except Queue.Empty:
                return

    def _decode_agents_data(self, block):
        """
        decode agents jsons, count diff
        """
        collect = []
        for chunk in block.split('\n'):
            if chunk:
                try:
                    prepared_results = {}
                    jsn = json.loads(chunk.strip('\n'))
                    for ts, values in jsn.iteritems():
                        for key, value in values.iteritems():
                            decoded_key = decoder.find_common_names(key)
                            if decoded_key in decoder.diff_metrics:
                                if self.prev_check:
                                    try:
                                        value = jsn[ts][key] - self.prev_check[key]
                                    except KeyError:
                                        logger.debug(
                                            'There is no diff value for metric %s.\n'
                                            'Timestamp: %s. Is it initial data?', key, ts, exc_info=True
                                        )
                                        value = 0
                                    prepared_results[decoded_key] = value
                            else:
                                prepared_results[decoded_key] = value
                        self.prev_check = jsn[ts]
                        collect.append((ts, prepared_results))
                except ValueError:
                    logger.info('Unable to decode monitoring json: %s', block, exc_info=True)
                except:
                    logger.error('Exception trying to parse monitoring agent data', exc_info=True)
        if collect:
            return collect