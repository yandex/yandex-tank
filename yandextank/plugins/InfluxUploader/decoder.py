import time


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
        points = []
        for second_data in data:
            timestamp = second_data["timestamp"]
            for host, host_data in second_data["data"].iteritems():
                points += [{
                    "measurement": "monitoring",
                    "tags": {
                        "tank": self.tank_tag,
                        "uuid": self.uuid,
                        "host": host,
                        "comment": host_data["comment"],
                    },
                    "time": timestamp,
                    "fields": {  # quantiles
                        metric: value
                        for metric, value in host_data["metrics"].iteritems()
                    },
                }]
        return points

    def decode_aggregate_labeled(self, data, stat, prefix):
        timestamp = int(data["ts"])
        points = []
        # overall quantiles w/ __OVERALL__ label
        points += [
            {
                "measurement": prefix + "overall_quantiles",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                    "label": "__OVERALL__"
                },
                "time": timestamp,
                "fields": {
                    'q' + str(q): value / 1000.0
                    for q, value in zip(data["overall"]["interval_real"]["q"]["q"],
                                        data["overall"]["interval_real"]["q"]["value"])
                },
            }
        ]
        for key, value in data["tagged"].items():
            points += [{
                "measurement": prefix + "overall_quantiles",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                    "label": key
                },
                "time": timestamp,
                "fields": {  # quantiles
                    'q' + str(q): value / 1000.0
                    for q, value in zip(value["interval_real"]["q"]["q"],
                                        value["interval_real"]["q"]["value"])
                },
            }, {
                "measurement": prefix + "overall_meta",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                    "label": key,
                },
                "time": timestamp,
                "fields": {
                    "active_threads": stat["metrics"]["instances"],
                    "RPS": value["interval_real"]["len"],
                    "planned_requests": float(stat["metrics"]["reqps"]),
                },
            }, {
                "measurement": prefix + "net_codes",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                    "label": key
                },
                "time": timestamp,
                "fields": {
                    str(code): int(cnt)
                    for code, cnt in value["net_code"]["count"].items()
                },
            }, {
                "measurement": prefix + "proto_codes",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                    "label": key
                },
                "time": timestamp,
                "fields": {
                    str(code): int(cnt)
                    for code, cnt in value["proto_code"]["count"].items()
                },
            },
            ]
        return points

    def decode_aggregate(self, data, stat):
        timestamp = int(data["ts"])
        points = [
            {
                "measurement": "overall_quantiles",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {  # quantiles
                    'q' + str(q): value / 1000.0
                    for q, value in zip(data["overall"]["interval_real"]["q"]["q"],
                                        data["overall"]["interval_real"]["q"]["value"])
                },
            }, {
                "measurement": "overall_meta",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {
                    "active_threads": stat["metrics"]["instances"],
                    "RPS": data["overall"]["interval_real"]["len"],
                    "planned_requests": float(stat["metrics"]["reqps"]),
                },
            }, {
                "measurement": "net_codes",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {
                    str(code): int(cnt)
                    for code, cnt in data["overall"]["net_code"]["count"].items()
                },
            }, {
                "measurement": "proto_codes",
                "tags": {
                    "tank": self.tank_tag,
                    "uuid": self.uuid,
                },
                "time": timestamp,
                "fields": {
                    str(code): int(cnt)
                    for code, cnt in data["overall"]["proto_code"]["count"].items()
                },
            },
        ]
        return points
