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

def decode_monitoring(data):
    data_items = (
        mon_decoder.decode_line(line)
        for line in data.splitlines()
        if line.strip()
    )
    result = {}
    for host, metrics, _, ts in data_items:
        host_metrics = result \
          .setdefault(int(ts), {}) \
          .setdefault("monitoring", {}) \
          .setdefault(host, {})
        for metric_name, value in metrics.iteritems():
            if '_' in metric_name:
                group, metric_name = metric_name.split('_', 1)
            else:
                group = metric_name
            host_metrics.setdefault(group, {})[metric_name] = parse_number(value)
    return result

def decode_aggregate(data):
    return {
        uts(data.time): {"responses":{
          "overall": data.overall.__getstate__(),
          "cumulative": data.cumulative.__getstate__(),
        }},
    }
