# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import StringIO
import copy
import json
import logging
import os
import pwd
import socket
import sys

from .client import OverloadClient
from ..Autostop import Plugin as AutostopPlugin
from ..Console import Plugin as ConsolePlugin
from ..JMeter import Plugin as JMeterPlugin
from ..Monitoring import Plugin as MonitoringPlugin
# from ..Pandora import Plugin as PandoraPlugin
from ..Phantom import Plugin as PhantomPlugin
from ...common.interfaces import AbstractPlugin,\
    MonitoringDataListener, AggregateResultListener, AbstractInfoWidget

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    """
    Yandex Overload analytics service client (https://overload.yandex.net)
    """
    SECTION = 'overload'
    RC_STOP_FROM_WEB = 8

    def __init__(self, core):
        super(Plugin, self).__init__(core)
        self.locks_list_dict = {}
        self.api_client = OverloadClient()
        self.jobno = None
        self.operator = ''
        self.retcode = -1
        self.copy_config = None
        self.jobno_file = None
        self.target = None
        self.lock_target_duration = None
        self.locks_list_cfg = None
        self.task = None
        self.job_name = None
        self.job_dsc = None
        self.notify_list = None
        self.version_tested = None
        self.regression_component = None
        self.is_regression = None
        self.ignore_target_lock = None
        self.port = None
        self.mon = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        opts = [
            "api_address",
            "task",
            "job_name",
            "job_dsc",
            "notify",
            "ver",
        ]
        opts += [
            "component",
            "regress",
            "operator",
            "copy_config_to",
            "jobno_file",
        ]
        opts += ["token_file"]
        return opts

    @staticmethod
    def read_token(filename):
        if filename:
            logger.debug("Trying to read token from %s", filename)
            try:
                with open(filename, 'r') as handle:
                    data = handle.read().strip()
                    logger.info(
                        "Read authentication token from %s, "
                        "token length is %d bytes", filename, len(str(data)))
            except IOError:
                logger.error(
                    "Failed to read Overload API token from %s", filename)
                logger.info(
                    "Get your Overload API token from https://overload.yandex.net and provide it via 'overload.token_file' parameter"
                )
                raise RuntimeError("API token error")
            return data
        else:
            logger.error("Overload API token filename is not defined")
            logger.info(
                "Get your Overload API token from https://overload.yandex.net and provide it via 'overload.token_file' parameter"
            )
            raise RuntimeError("API token error")

    def configure(self):
        aggregator = self.core.job.aggregator_plugin
        aggregator.add_result_listener(self)

        self.api_client.set_api_address(self.get_option("api_address"))
        self.api_client.set_api_timeout(self.get_option("api_timeout", 30))
        self.api_client.set_api_token(
            self.read_token(self.get_option("token_file", "")))
        self.task = self.get_option("task", "DEFAULT")
        self.job_name = unicode(
            self.get_option("job_name", "none").decode("utf8"))
        if self.job_name == "ask" and sys.stdin.isatty():
            self.job_name = unicode(
                raw_input("Please, enter job_name: ").decode("utf8"))
        self.job_dsc = unicode(self.get_option("job_dsc", "").decode("utf8"))
        if self.job_dsc == "ask" and sys.stdin.isatty():
            self.job_dsc = unicode(
                raw_input("Please, enter job_dsc: ").decode("utf8"))
        self.notify_list = self.get_option("notify", "").split(" ")
        self.version_tested = unicode(self.get_option("ver", ""))
        self.regression_component = unicode(self.get_option("component", ""))
        self.is_regression = self.get_option("regress", "0")
        self.operator = self.get_option("operator", self.operator)
        if not self.operator:
            try:
                # Clouds and some virtual envs may fail this
                self.operator = pwd.getpwuid(os.geteuid())[0]
            except:
                logger.warning('failed to getpwuid.', exc_into=True)
                self.operator = 'unknown'
        self.copy_config = self.get_option("copy_config_to", "")
        self.jobno_file = self.get_option("jobno_file", "")

        if self.core.job.monitoring_plugin:
            self.mon = self.core.job.monitoring_plugin
            if self.mon.monitoring:
                self.mon.monitoring.add_listener(self)

        self.__save_conf()

    def prepare_test(self):
        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except KeyError:
            logger.debug("Console plugin not found", exc_info=True)
            console = None

        if console:
            console.add_info_widget(JobInfoWidget(self))
            console.remote_translator = self

        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
            info = phantom.get_info()
            self.target = info.address
        except (KeyError, AttributeError) as ex:
            logger.debug("No phantom plugin to get target info: %s", ex)
            self.target = socket.getfqdn()

        self.__save_conf()

    def start_test(self):
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
            info = phantom.get_info()
            self.target = info.address
            port = info.port
            instances = info.instances
            tank_type = 1 if info.tank_type == "http" else 2
            # FIXME why don't we use resource_opener here?
            if info.ammo_file.startswith(
                    "http://") or info.ammo_file.startswith("https://"):
                ammo_path = info.ammo_file
            else:
                ammo_path = os.path.realpath(info.ammo_file)
            loadscheme = [] if isinstance(
                info.rps_schedule, unicode) else info.rps_schedule
            loop_count = info.loop_count
        except (KeyError, AttributeError) as ex:
            logger.debug("No phantom plugin to get target info: %s", ex)
            self.target = socket.getfqdn()
            port = 80
            instances = 1
            tank_type = 1
            ammo_path = ''
            loadscheme = []
            loop_count = 0

        try:
            jmeter = self.core.get_plugin_of_type(JMeterPlugin)
            ammo_path = jmeter.original_jmx
        except KeyError as ex:
            logger.debug("No jmeter plugin to get info: %s", ex)

        # try:
        #     pandora = self.core.get_plugin_of_type(PandoraPlugin)
        #     # TODO: get info from Pandora here
        # except KeyError as ex:
        #     logger.debug("No pandora plugin to get info: %s", ex)

        detailed_field = "interval_real"

        logger.info("Detected target: %s", self.target)

        self.jobno = self.api_client.new_job(
            self.task, self.operator,
            socket.getfqdn(), self.target, port, loadscheme, detailed_field,
            self.notify_list)
        web_link = "%s%s" % (self.api_client.address, self.jobno)
        logger.info("Web link: %s", web_link)
        self.publish("jobno", self.jobno)
        self.publish("web_link", web_link)
        self.make_symlink(self.jobno)
        self.set_option("jobno", str(self.jobno))
        if self.jobno_file:
            logger.debug("Saving jobno to: %s", self.jobno_file)
            fdes = open(self.jobno_file, 'w')
            fdes.write(str(self.jobno))
            fdes.close()

        self.api_client.edit_job_metainfo(
            self.jobno, self.job_name, self.job_dsc, instances, ammo_path,
            loop_count, self.version_tested, self.is_regression,
            self.regression_component, tank_type, " ".join(sys.argv), 0)

        self.__save_conf()

    def is_test_finished(self):
        return self.retcode

    def end_test(self, retcode):
        self.__save_conf()
        return retcode

    def post_process(self, rc):
        if self.jobno:
            try:
                self.api_client.close_job(self.jobno, rc)
            except Exception:  # pylint: disable=W0703
                logger.warning("Failed to close job", exc_info=True)

            logger.info("Web link: %s%s", self.api_client.address, self.jobno)

            autostop = None
            try:
                autostop = self.core.get_plugin_of_type(AutostopPlugin)
            except KeyError:
                logger.debug("No autostop plugin loaded", exc_info=True)

            if autostop and autostop.cause_criterion:
                rps = 0
                if autostop.cause_criterion.cause_second:
                    rps = autostop.cause_criterion.cause_second[1]["metrics"][
                        "reqps"]
                    if not rps:
                        rps = autostop.cause_criterion.cause_second[0][
                            "overall"]["interval_real"]["len"]
                self.api_client.set_imbalance_and_dsc(
                    self.jobno, rps, autostop.cause_criterion.explain())

            else:
                logger.debug("No autostop cause detected")
        self.__save_conf()
        return rc

    def __send_data(self, data_item, stat_item):
        if self.retcode < 0 and not self.api_client.push_test_data(
                self.jobno, data_item, stat_item):
            logger.warn("The test was stopped from Web interface")
            self.retcode = self.RC_STOP_FROM_WEB

    def on_aggregated_data(self, data, stats):
        """
        @data: aggregated data
        @stats: stats about gun
        """
        if not self.jobno:
            logger.warning("No jobNo gained yet")
            return
        self.__send_data(data, stats)

    def monitoring_data(self, data_list):
        if not self.jobno:
            logger.debug("No jobNo gained yet")
            return

        if self.retcode < 0:
            if "Telegraf" in self.core.job.monitoring_plugin.__module__:
                self.api_client.push_monitoring_data(
                    self.jobno, json.dumps(data_list))
            elif "Monitoring" in self.core.job.monitoring_plugin.__module__:
                [
                    self.api_client.push_monitoring_data(self.jobno, data)
                    for data in data_list if data
                ]
        else:
            logger.warn("The test was stopped from Web interface")

    def __save_conf(self):
        if self.copy_config:
            self.core.config.flush(self.copy_config)

        config = copy.copy(self.core.config.config)

        try:
            mon = self.core.get_plugin_of_type(MonitoringPlugin)
            config_filename = mon.config
            if config_filename and config_filename not in ['none', 'auto']:
                with open(config_filename) as config_file:
                    config.set(
                        MonitoringPlugin.SECTION, "config_contents",
                        config_file.read())
        except Exception:  # pylint: disable=W0703
            logger.debug("Can't get monitoring config", exc_info=True)

        output = StringIO.StringIO()
        config.write(output)
        if self.jobno:
            try:
                self.api_client.send_config_snapshot(
                    self.jobno, output.getvalue())
            except Exception:  # pylint: disable=W0703
                logger.debug("Can't send config snapshot: %s", exc_info=True)

    def send_console(self, text):
        try:
            self.api_client.send_console(self.jobno, text)
        except Exception:  # pylint: disable=W0703
            logger.debug("Can't send console snapshot: %s", exc_info=True)

    def make_symlink(self, name):
        PLUGIN_DIR = os.path.join(self.core.artifacts_base_dir, self.SECTION)
        if not os.path.exists(PLUGIN_DIR):
            os.makedirs(PLUGIN_DIR)
        os.symlink(self.core.artifacts_dir, os.path.join(PLUGIN_DIR, str(name)))

    def _core_with_tank_api(self):
        """
        Return True if we are running under Tank API
        """
        api_found = False
        try:
            import yandex_tank_api.worker  # pylint: disable=F0401
        except ImportError:
            logger.debug("Attempt to import yandex_tank_api.worker failed")
        else:
            api_found = isinstance(self.core, yandex_tank_api.worker.TankCore)
        logger.debug(
            "We are%s running under API server", ""
            if api_found else " likely not")
        return api_found


class JobInfoWidget(AbstractInfoWidget):
    def __init__(self, sender):
        AbstractInfoWidget.__init__(self)
        self.owner = sender

    def get_index(self):
        return 1

    def render(self, screen):
        template = "Author: " + screen.markup.RED + "%s" + \
            screen.markup.RESET + \
            "%s\n   Job: %s %s\n  Web: %s%s"
        data = (
            self.owner.operator[:1], self.owner.operator[1:], self.owner.jobno,
            self.owner.job_name, self.owner.api_client.address,
            self.owner.jobno)

        return template % data
