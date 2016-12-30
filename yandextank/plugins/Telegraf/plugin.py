"""Module provides target monitoring
metrics collector - influxdata's `telegraf` - https://github.com/influxdata/telegraf/
backward compatibility with yandextank's Monitoring module configuration and tools.
"""

import datetime
import fnmatch
import json
import logging
import os
import time
from ...common.resource import manager as resource
from ...common.interfaces import MonitoringDataListener, \
    AbstractPlugin, AbstractInfoWidget
from ...common.util import expand_to_seconds

from ..Autostop import Plugin as AutostopPlugin, AbstractCriterion
from ..Console import Plugin as ConsolePlugin
from ..Telegraf.collector import MonitoringCollector

import sys
if sys.version_info[0] < 3:
    from ConfigParser import NoOptionError
else:
    from configparser import NoOptionError

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin):
    """  resource mon plugin  """

    SECTION = 'telegraf'  # may be redefined to 'monitoring' sometimes.

    def __init__(self, core):
        super(Plugin, self).__init__(core)
        self.jobno = None
        self.default_target = None
        self.default_config = "{path}/config/monitoring_default_config.xml".format(
            path=os.path.dirname(__file__))
        self.config = None
        self.process = None
        self.monitoring = MonitoringCollector()
        self.die_on_fail = True
        self.data_file = None
        self.mon_saver = None

    @staticmethod
    def get_key():
        return __file__

    def start_test(self):
        if self.monitoring:
            self.monitoring.load_start_time = time.time()
            logger.debug(
                "load_start_time = %s", self.monitoring.load_start_time)

    def get_available_options(self):
        return ["config", "default_target", "ssh_timeout"]

    def __detect_configuration(self):
        """
        we need to be flexible in order to determine which plugin's configuration
        specified and make appropriate configs to metrics collector

        :return: SECTION name or None for defaults
        """
        try:
            is_telegraf = self.core.get_option('telegraf', "config", None)
        except NoOptionError:
            is_telegraf = None
        try:
            is_monitoring = self.core.get_option('monitoring', "config", None)
        except NoOptionError:
            is_monitoring = None

        if is_telegraf and is_monitoring:
            raise ValueError(
                'Both telegraf and monitoring configs specified. '
                'Clean up your config and delete one of them')
        if is_telegraf and not is_monitoring:
            return 'telegraf'
        if not is_telegraf and is_monitoring:
            return 'monitoring'
        if not is_telegraf and not is_monitoring:
            # defaults target logic
            try:
                is_telegraf_dt = self.core.get_option(
                    'telegraf', "default_target", None)
            except NoOptionError:
                is_telegraf_dt = None
            try:
                is_monitoring_dt = self.core.get_option(
                    'monitoring', "default_target", None)
            except:
                is_monitoring_dt = None
            if is_telegraf_dt and is_monitoring_dt:
                raise ValueError(
                    'Both telegraf and monitoring default targets specified. '
                    'Clean up your config and delete one of them')
            if is_telegraf_dt and not is_monitoring_dt:
                return
            if not is_telegraf_dt and is_monitoring_dt:
                self.core.set_option(
                    "telegraf", "default_target", is_monitoring_dt)
            if not is_telegraf_dt and not is_monitoring_dt:
                return

    def configure(self):
        self.detected_conf = self.__detect_configuration()
        if self.detected_conf:
            logging.info(
                'Detected monitoring configuration: %s', self.detected_conf)
            self.SECTION = self.detected_conf
        self.config = self.get_option("config", "auto").strip()
        self.default_target = self.get_option("default_target", "localhost")
        if self.config.lower() == "none":
            self.monitoring = None
            self.die_on_fail = False
            return

        # FIXME [legacy] backward compatibility with Monitoring module
        # configuration below.
        self.monitoring.ssh_timeout = expand_to_seconds(
            self.get_option("ssh_timeout", "5s"))

        # FIXME [legacy] handle raw XML config in .ini file
        if self.config[0] == "<":
            config_contents = self.config
        # handle http/https url or file path
        else:
            if self.config.lower() == "auto":
                self.die_on_fail = False
                with open(
                        resource.resource_filename(self.default_config),
                        'rb') as def_config:
                    config_contents = def_config.read()
            else:
                with open(resource.resource_filename(self.config),
                          'rb') as config:
                    config_contents = config.read()

        # dump config contents into a file
        xmlfile = self.core.mkstemp(".xml", "monitoring_")
        self.core.add_artifact_file(xmlfile)
        with open(
                xmlfile, "wb"
        ) as f:  # output file should be in binary mode to support py3
            f.write(config_contents)
        self.config = xmlfile

        try:
            autostop = self.core.get_plugin_of_type(AutostopPlugin)
            autostop.add_criterion_class(MetricHigherCriterion)
            autostop.add_criterion_class(MetricLowerCriterion)
        except KeyError:
            logger.debug(
                "No autostop plugin found, not adding instances criterion")

    def prepare_test(self):
        if not self.config or self.config.lower() == 'none':
            return

        if "Phantom" in self.core.job.generator_plugin.__module__:
            phantom = self.core.job.generator_plugin
            if phantom.phout_import_mode:
                logger.info("Phout import mode, disabling monitoring")
                self.config = None
                self.monitoring = None

            info = phantom.get_info()
            if info:
                self.default_target = info.address
                logger.debug(
                    "Changed monitoring target to %s", self.default_target)

        self.monitoring.config = self.config
        if self.default_target:
            self.monitoring.default_target = self.default_target

        # FIXME json report already save this artifact, fix pls
        self.data_file = self.core.mkstemp(".data", "monitoring_overall_")
        self.mon_saver = SaveMonToFile(self.data_file)
        self.monitoring.add_listener(self.mon_saver)
        self.core.add_artifact_file(self.data_file)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except Exception as ex:
            logger.debug("Console not found: %s", ex)
            console = None
        if console:
            widget = MonitoringWidget(self)
            console.add_info_widget(widget)
            self.monitoring.add_listener(widget)

        try:
            self.monitoring.prepare()
            self.monitoring.start()
            count = 0
            while not self.monitoring.first_data_received and count < 15 * 5:
                time.sleep(0.2)
                self.monitoring.poll()
                count += 1
        except:
            logger.error("Could not start monitoring", exc_info=True)
            if self.die_on_fail:
                raise
            else:
                self.monitoring = None

    def is_test_finished(self):
        if self.monitoring:
            data_len = self.monitoring.poll()
            logger.debug("Monitoring got %s lines", data_len)
        return -1

    def end_test(self, retcode):
        logger.info("Finishing monitoring")
        if self.monitoring:
            self.monitoring.stop()
            for log in self.monitoring.artifact_files:
                self.core.add_artifact_file(log)

            while self.monitoring.send_data:
                logger.info("Sending monitoring data rests...")
                self.monitoring.send_collected_data()
        if self.mon_saver:
            self.mon_saver.close()
        return retcode


class SaveMonToFile(MonitoringDataListener):
    """
    Default listener - saves data to file
    """

    def __init__(self, out_file):
        MonitoringDataListener.__init__(self)
        if out_file:
            self.store = open(out_file, 'w')

    def monitoring_data(self, data):
        self.store.write(json.dumps(data))
        self.store.write('\n')
        self.store.flush()

    def close(self):
        """ close open files """
        logger.debug("Closing monitoring file")
        if self.store:
            self.store.close()


class MonitoringWidget(AbstractInfoWidget, MonitoringDataListener):
    """
    Screen widget
    """

    def __init__(self, owner):
        AbstractInfoWidget.__init__(self)
        self.owner = owner
        self.data = {}
        self.sign = {}
        self.time = {}
        self.max_metric_len = 0

    def get_index(self):
        return 50

    def __handle_data_items(self, host, data):
        """ store metric in data tree and calc offset signs

        sign < 0 is CYAN, means metric value is lower then previous,
        sign > 1 is YELLOW, means metric value is higher then prevoius,
        sign == 0 is WHITE, means initial or equal metric value
        """
        for metric, value in data.iteritems():
            if value == '':
                self.sign[host][metric] = -1
                self.data[host][metric] = value
            else:
                if not self.data[host].get(metric, None):
                    self.sign[host][metric] = 1
                elif float(value) > float(self.data[host][metric]):
                    self.sign[host][metric] = 1
                elif float(value) < float(self.data[host][metric]):
                    self.sign[host][metric] = -1
                else:
                    self.sign[host][metric] = 0
                self.data[host][metric] = "%.2f" % float(value)

    def monitoring_data(self, block):
        # block sample :
        # [{'timestamp': 1480536634,
        #   'data': {
        #     'some.hostname.tld': {
        #       'comment': '',
        #       'metrics': {
        #         'custom:diskio_reads': 0,
        #         'Net_send': 9922,
        #         'CPU_steal': 0,
        #         'Net_recv': 8489
        #       }
        #     }
        #   },
        #   ...
        # }]
        for chunk in block:
            host = chunk['data'].keys()[0]
            self.time[host] = chunk['timestamp']
            # if initial call, we create dicts w/ data and `signs`
            # `signs` used later to paint metrics w/ different colors
            if not self.data.get(host, None):
                self.data[host] = {}
                self.sign[host] = {}
                for key, value in chunk['data'][host]['metrics'].iteritems():
                    self.sign[host][key] = 0
                    self.data[host][key] = value
            else:
                self.__handle_data_items(host, chunk['data'][host]['metrics'])

    def render(self, screen):
        if not self.owner.monitoring:
            return "Monitoring is " + screen.markup.RED + "offline" + screen.markup.RESET
        else:
            res = "Monitoring is " + screen.markup.GREEN + \
                "online" + screen.markup.RESET + ":\n"
            for hostname, metrics in self.data.items():
                tm_stamp = datetime.datetime.fromtimestamp(
                    float(self.time[hostname])).strftime('%H:%M:%S')
                res += (
                    "   " + screen.markup.CYAN + "%s" + screen.markup.RESET +
                    " at %s:\n") % (hostname, tm_stamp)
                for metric, value in sorted(metrics.iteritems()):
                    if self.sign[hostname][metric] > 0:
                        value = screen.markup.YELLOW + value + screen.markup.RESET
                    elif self.sign[hostname][metric] < 0:
                        value = screen.markup.CYAN + value + screen.markup.RESET
                    res += "      %s%s: %s\n" % (
                        ' ' * (self.max_metric_len - len(metric)),
                        metric.replace('custom:', '').replace('_', ' '), value)

            return res.strip()


class AbstractMetricCriterion(AbstractCriterion, MonitoringDataListener):
    """ Parent class for metric criterion """

    def __init__(self, autostop, param_str):
        AbstractCriterion.__init__(self)
        try:
            self.mon = autostop.core.get_plugin_of_type(Plugin)
            if self.mon.monitoring:
                self.mon.monitoring.add_listener(self)
        except KeyError:
            logger.warning("No monitoring module, mon autostop disabled")
        self.triggered = False
        self.autostop = autostop

        self.host = param_str.split(',')[0].strip()
        self.metric = param_str.split(',')[1].strip()
        self.value_limit = float(param_str.split(',')[2])
        self.seconds_limit = expand_to_seconds(param_str.split(',')[3])
        self.last_second = None
        self.seconds_count = 0

    def monitoring_data(self, block):
        if self.triggered:
            return

        for chunk in block:
            host = chunk['data'].keys()[0]
            data = chunk['data'][host]['metrics']

            if not fnmatch.fnmatch(host, self.host):
                continue

            # some magic, converting custom metric names into names that was in
            # config
            for metric_name in data.keys():
                if metric_name.startswith('custom:'):
                    config_metric_name = metric_name.replace('custom:', '')
                    data[config_metric_name] = data.pop(metric_name)

            if self.metric not in data.keys() or not data[self.metric]:
                data[self.metric] = 0
            logger.debug(
                "Compare %s %s/%s=%s to %s",
                self.get_type_string(), host, self.metric, data[self.metric],
                self.value_limit)
            if self.comparison_fn(float(data[self.metric]), self.value_limit):
                if not self.seconds_count:
                    self.cause_second = self.last_second

                logger.debug(self.explain())

                self.seconds_count += 1
                if self.seconds_count >= self.seconds_limit:
                    logger.debug("Triggering autostop")
                    self.triggered = True
                    return
            else:
                self.seconds_count = 0

    def notify(self, data, stat):
        if self.seconds_count:
            self.autostop.add_counting(self)

        self.last_second = (data, stat)
        return self.triggered

    def comparison_fn(self, arg1, arg2):
        """ comparison function """
        raise NotImplementedError()


class MetricHigherCriterion(AbstractMetricCriterion):
    """ trigger if metric is higher than limit """

    def __init__(self, autostop, param_str):
        AbstractMetricCriterion.__init__(self, autostop, param_str)

    def get_rc(self):
        return 31

    @staticmethod
    def get_type_string():
        return 'metric_higher'

    def explain(self):
        items = (self.host, self.metric, self.value_limit, self.seconds_count)
        return "%s/%s metric value is higher than %s for %s seconds" % items

    def widget_explain(self):
        items = (
            self.host, self.metric, self.value_limit, self.seconds_count,
            self.seconds_limit)
        return "%s/%s > %s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit

    def comparison_fn(self, arg1, arg2):
        return arg1 > arg2


class MetricLowerCriterion(AbstractMetricCriterion):
    """ trigger if metric is lower than limit """

    def __init__(self, autostop, param_str):
        AbstractMetricCriterion.__init__(self, autostop, param_str)

    def get_rc(self):
        return 32

    @staticmethod
    def get_type_string():
        return 'metric_lower'

    def explain(self):
        items = (self.host, self.metric, self.value_limit, self.seconds_count)
        return "%s/%s metric value is lower than %s for %s seconds" % items

    def widget_explain(self):
        items = (
            self.host, self.metric, self.value_limit, self.seconds_count,
            self.seconds_limit)
        return "%s/%s < %s for %s/%ss" % items, float(
            self.seconds_count) / self.seconds_limit

    def comparison_fn(self, arg1, arg2):
        return arg1 < arg2
