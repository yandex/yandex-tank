import time
from yandextank.plugins.Monitoring.collector import MonitoringDataDecoder

mon_decoder = MonitoringDataDecoder()


def uts(dt):
    return int(time.mktime(dt.timetuple()))


class Decoder(object):
    def __init__(self, tank_tag, uuid):
        self.tank_tag = tank_tag
        self.uuid = uuid

    def decode_monitoring_item(self, item):
        host, metrics, _, ts = item
        return {
            "measurement": "monitoring",
            "tags": {
                "tank": self.tank_tag,
                "host": host,
                "uuid": self.uuid,
            },
            "time": ts,
            "fields": metrics,
        }

    def decode_monitoring(self, data):
        data_items = (
            mon_decoder.decode_line(line)
            for line in data.splitlines()
            if line.strip()
        )
        return [self.decode_monitoring_item(item) for item in data_items]

    def decode_aggregate(self, data):
        timestamp = uts(data.time)
        overall = data.overall.__getstate__()
        # cumulative = data.cumulative.__getstate__()
        points = [
            {
                "measurement": "overall_quantiles",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {str(k): v for k, v in overall['quantiles'].items()},
            }, {
                "measurement": "overall_meta",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {
                    k: overall[k]
                    for k in ["RPS", "active_threads", "planned_requests"]
                    if k in overall
                },
            },
        ]
        if overall['net_codes']:
            points += [{
                "measurement": "net_codes",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {str(k): v for k, v in overall['net_codes'].items()},
            }]
        if overall['http_codes']:
            points += [{
                "measurement": "http_codes",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {str(k): v for k, v in overall['http_codes'].items()},
            }]
        return points
