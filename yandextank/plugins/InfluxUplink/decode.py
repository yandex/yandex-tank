import time
from yandextank.plugins.Monitoring.collector import MonitoringDataDecoder

mon_decoder = MonitoringDataDecoder()


def uts(dt):
    return int(time.mktime(dt.timetuple()))


def parse_number(val):
    try:
        return float(val)
    except ValueError:
        return None


def decode_monitoring_item(item):
    host, metrics, _, ts = item
    return {
        "measurement": "monitoring",
        "tags": {
            "tank": "server01",
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


def decode_aggregate(data):
    timestamp = uts(data.time)
    overall = data.overall.__getstate__()
    # cumulative = data.cumulative.__getstate__()
    points = [
        {
            "measurement": "overall_quantiles",
            "tags": {
                "host": "server01",
            },
            "time": timestamp,
            "fields": {str(k): v for k, v in overall['quantiles'].items()},
        }, {
            "measurement": "overall_meta",
            "tags": {
                "host": "server01",
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
                "host": "server01",
            },
            "time": timestamp,
            "fields": {str(k): v for k, v in overall['net_codes'].items()},
        }]
    if overall['http_codes']:
        points += [{
            "measurement": "http_codes",
            "tags": {
                "host": "server01",
            },
            "time": timestamp,
            "fields": {str(k): v for k, v in overall['http_codes'].items()},
        }]
    return points
