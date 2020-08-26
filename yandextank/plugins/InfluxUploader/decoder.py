import time


def uts(dt):
    return int(time.mktime(dt.timetuple()))


class Decoder(object):
    """
    Decode metrics incoming from tank into points for InfluxDB client

    Parameters
    ----------
    parent_tags : dict
        common per-test tags
    tank_tag : str
        tank identifier tag
    uuid : str
        test id tag
    labeled : bool
        detailed stats for each label
    histograms : bool
        response time histograms measurements
    """
    def __init__(self, tank_tag, uuid, parent_tags, labeled, histograms):
        self.labeled = labeled
        initial_tags = {
            "tank": tank_tag,
            "uuid": uuid
        }
        initial_tags.update(parent_tags)
        self.tags = initial_tags
        self.histograms = histograms

    def set_uuid(self, id_):
        self.tags['uuid'] = id_

    def decode_monitoring(self, data):
        """
        The reason why we have two separate methods for monitoring
        and aggregates is a strong difference in incoming data.
        """
        points = list()
        for second_data in data:
            for host, host_data in second_data["data"].items():
                points.append(
                    self.__make_points(
                        "monitoring",
                        {"host": host, "comment": host_data.get("comment")},
                        second_data["timestamp"],
                        {
                            # cast int to float. avoid https://github.com/yandex/yandex-tank/issues/776
                            metric: float(value) if isinstance(value, int) else value
                            for metric, value in host_data["metrics"].items()
                        }
                    )
                )
        return points

    def decode_aggregates(self, aggregated_data, gun_stats, prefix):
        ts = aggregated_data["ts"]
        points = list()
        # stats overall w/ __OVERALL__ label
        points += self.__make_points_for_label(
            ts,
            aggregated_data["overall"],
            "__OVERALL__",
            prefix,
            gun_stats
        )
        # detailed stats per tag
        if self.labeled:
            for label, aggregated_data_by_tag in aggregated_data["tagged"].items():
                points += self.__make_points_for_label(
                    ts,
                    aggregated_data_by_tag,
                    label,
                    prefix,
                    gun_stats
                )
        return points

    def __make_points_for_label(self, ts, data, label, prefix, gun_stats):
        """x
        Make a set of points for `this` label

        overall_quantiles, overall_meta, net_codes, proto_codes, histograms
        """
        label_points = list()

        label_points.extend(
            (
                # overall quantiles for label
                self.__make_points(
                    prefix + "overall_quantiles",
                    {"label": label},
                    ts,
                    self.__make_quantile_fields(data)
                ),
                # overall meta (gun status) for label
                self.__make_points(
                    prefix + "overall_meta",
                    {"label": label},
                    ts,
                    self.__make_overall_meta_fields(data, gun_stats)
                ),
                # net codes for label
                self.__make_points(
                    prefix + "net_codes",
                    {"label": label},
                    ts,
                    self.__make_netcodes_fields(data)
                ),
                # proto codes for label
                self.__make_points(
                    prefix + "proto_codes",
                    {"label": label},
                    ts,
                    self.__make_protocodes_fields(data)
                )
            )
        )
        # histograms, one row for each bin
        if self.histograms:
            for bin_, count in zip(data["interval_real"]["hist"]["bins"],
                                   data["interval_real"]["hist"]["data"]):
                label_points.append(
                    self.__make_points(
                        prefix + "histograms",
                        {"label": label},
                        ts,
                        {"bin": bin_, "count": count}
                    )
                )
        return label_points

    @staticmethod
    def __make_quantile_fields(data):
        return {
            'q' + str(q): value / 1000.0
            for q, value in zip(data["interval_real"]["q"]["q"],
                                data["interval_real"]["q"]["value"])
        }

    @staticmethod
    def __make_overall_meta_fields(data, stats):
        return {
            "active_threads": stats["metrics"]["instances"],
            "RPS": data["interval_real"]["len"],
            "planned_requests": float(stats["metrics"]["reqps"]),
        }

    @staticmethod
    def __make_netcodes_fields(data):
        return {
            str(code): int(cnt)
            for code, cnt in data["net_code"]["count"].items()
        }

    @staticmethod
    def __make_protocodes_fields(data):
        return {
            str(code): int(cnt)
            for code, cnt in data["proto_code"]["count"].items()
        }

    def __make_points(self, measurement, additional_tags, ts, fields):
        """
        Parameters
        ----------
        measurement : string
            measurement type (e.g. monitoring, overall_meta, net_codes, proto_codes, overall_quantiles)
        additional_tags : dict
            custom additional tags for this points
        ts : integer
            timestamp
        fields : dict
            influxdb columns

        Returns
        -------
        dict
            points for InfluxDB client
        """
        tags = self.tags.copy()
        tags.update(additional_tags)
        return {
            "measurement": measurement,
            "tags": tags,
            "time": int(ts),
            "fields": fields,
        }
