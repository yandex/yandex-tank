import time
from Tank.MonCollector.collector import MonitoringDataDecoder

mon_decoder = MonitoringDataDecoder()

def uts(dt):
    return int(time.mktime(dt.timetuple()))

def parse_number(val):
    try:
        return float(val)
    except ValueError:
        return None

def decode_monitoring(data):
    data_items = (
        mon_decoder.decode_line(line)
        for line in data.splitlines()
        if line.strip()
    )
    data = {
        int(ts): {"monitoring": {host: {m: parse_number(v) for m, v in metrics.iteritems()}}}
        for host, metrics, _, ts in data_items
    }
    return data

def decode_aggregate(data):
    return {
        uts(data.time): {"responses":{"overall": data.overall.__getstate__()}},
    }
