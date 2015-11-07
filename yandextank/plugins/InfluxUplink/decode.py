import time
from yandextank.plugins.Monitoring.collector import MonitoringDataDecoder

mon_decoder = MonitoringDataDecoder()


def uts(dt):
    return int(time.mktime(dt.timetuple()))


def decode_monitoring_item(item, tank):
    host, metrics, _, ts = item
    return {
        "measurement": "monitoring",
        "tags": {
            "tank": tank,
            "host": item[0]
        },
        "time": ts,
        "fields": metrics,
    }


def decode_monitoring(data):
    data_items = (
        mon_decoder.decode_line(line)
        for line in data.splitlines()
        if line.strip()
    )
    return [decode_monitoring_item(item) for item in data_items]


def decode_aggregate(data, tank):
    timestamp = uts(data.time)
    overall = data.overall.__getstate__()
    # cumulative = data.cumulative.__getstate__()
    points = [
        {
            "measurement": "overall_quantiles",
            "tags": {
                "tank": tank,
            },
            "time": timestamp,
            "fields": {str(k): v for k, v in overall['quantiles'].items()},
        }, {
            "measurement": "overall_meta",
            "tags": {
                "tank": tank,
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
                "tank": tank,
            },
            "time": timestamp,
            "fields": {str(k): v for k, v in overall['net_codes'].items()},
        }]
    if overall['http_codes']:
        points += [{
            "measurement": "http_codes",
            "tags": {
                "tank": tank,
            },
            "time": timestamp,
            "fields": {str(k): v for k, v in overall['http_codes'].items()},
        }]
    return points
