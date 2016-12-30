import os.path
import seaborn

from ...common.interfaces import AbstractPlugin, MonitoringDataListener, AggregateResultListener

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa:E402

_ALL_ = "All"
_CHARTSETS = {
    "cpu-cpu-": {
        "CPU": _ALL_
    },
    "net-": {
        "Network": {"bytes_sent", "bytes_recv"}
    },
    "diskio-": {
        "Disk IO": {"read_bytes", "write_bytes"},
        "Disk latency": {"read_time", "write_time"}
    },
}
_CUSTOM_PREFIX = "custom:"
_REPORT_FILE_OPTION = "report_file"


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    """
        Generates simple shooting report in svg format
    """

    SECTION = "svgreport"

    def __init__(self, core):
        super(Plugin, self).__init__(core)

    def get_available_options(self):
        return [_REPORT_FILE_OPTION]

    def configure(self):
        self.__report_path = self.get_option(_REPORT_FILE_OPTION, "report.svg")
        if os.path.split(self.__report_path)[0] or os.path.splitdrive(
                self.__report_path)[0]:
            raise Exception("Only simple file names supported")

        self.__shooting_data = []
        self.__monitoring_data = []
        self.core.job.subscribe_plugin(self)

    def on_aggregated_data(self, data, stats):
        if data:
            self.__shooting_data.append(data)

    def monitoring_data(self, data_list):
        if data_list:
            self.__monitoring_data.extend(data_list)

    def post_process(self, retcode):
        monitoring_chartsets = self.__get_monitoring_chartsets()
        min_x = self.__shooting_data[0][
            "ts"]  # sync start of shooting and start of monitoring

        seaborn.set(style="whitegrid", palette="Set2")
        seaborn.despine()

        plot_count = len(monitoring_chartsets) + 1
        plt.figure(figsize=(16, 3 * plot_count))

        # testing
        plt.subplot(plot_count, 1, 1)
        plt.title("RPS")
        x, y = self.__get_shooting_coords("proto_code", min_x)
        for variant in x:
            plt.plot(x[variant], y[variant], label=variant)
        plt.gca().legend(fontsize="x-small")

        # monitoring
        for plot_num, chartset_data in enumerate(
                sorted(monitoring_chartsets.iteritems()), 1):
            chartset_title, signals = chartset_data

            plt.subplot(plot_count, 1, plot_num + 1)
            plt.title(chartset_title)

            for signal_name, signal_suffix in signals:
                x, y = self.__get_monitoring_coords(signal_name, min_x)
                plt.plot(x, y, label=signal_suffix)
            plt.gca().legend(fontsize="x-small")

        plt.tight_layout()
        plt.suptitle("Shooting results", fontsize=16, fontweight="bold")
        plt.subplots_adjust(top=0.96)
        plt.savefig(os.path.join(self.core.artifacts_dir, self.__report_path))

    def __find_monitoring_chartset(self, signal_prefix, signal_suffix):
        """
            Tune chartset content

            Some of signals should be skipped, and other should be distributed between
            two chartsets
        """

        if signal_prefix.startswith(_CUSTOM_PREFIX):
            signal_prefix = signal_prefix[len(_CUSTOM_PREFIX):]

        for chartset_prefix, chartset_data in _CHARTSETS.iteritems():
            if signal_prefix.startswith(chartset_prefix):
                for chartset_title, chartset_signals in chartset_data.iteritems(
                ):
                    if chartset_signals is _ALL_ or signal_suffix in chartset_signals:
                        return "{} {}".format(
                            chartset_title,
                            signal_prefix[len(chartset_prefix):])
                else:
                    return None
        else:
            return signal_prefix

    def __get_monitoring_chartsets(self):
        """Analyze monitoring signals and organize chartsets"""

        chartsets = {}
        for p in self.__monitoring_data:
            metrics = p["data"]["localhost"]["metrics"]
            for signal_name, signal_value in metrics.iteritems():
                if not signal_value:
                    continue

                signal_prefix, signal_suffix = signal_name.split("_", 1)
                chartset_title = self.__find_monitoring_chartset(
                    signal_prefix, signal_suffix)
                if not chartset_title:
                    continue

                chartsets.setdefault((chartset_title), set()).add(
                    (signal_name, signal_suffix))

        return chartsets

    def __get_monitoring_coords(self, signal_name, min_x):
        """Return values for x and y axes of plot for specified signal"""

        x, y = [], []
        for p in self.__monitoring_data:
            metrics = p["data"]["localhost"]["metrics"]
            timestamp = p["timestamp"]
            if signal_name in metrics and timestamp >= min_x:
                x.append(timestamp - min_x)
                y.append(metrics[signal_name])
        return x, y

    def __get_shooting_coords(self, signal_name, min_x):
        """Return values for x and y axes of plot for specified signal"""

        x = {}
        y = {}
        for data in self.__shooting_data:
            timestamp = data["ts"]
            for variant, count in data["overall"][signal_name][
                    "count"].iteritems():
                x.setdefault(variant, []).append(timestamp - min_x)
                y.setdefault(variant, []).append(count)
        return x, y
