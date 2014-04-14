""" Module to perform distributed tests """
# TODO: how to deal with remote monitoring data?
import fnmatch
import os
import random
import time
import traceback
import datetime

from Tank.Plugins import ConsoleScreen
from Tank.Plugins.ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget
from tankcore import AbstractPlugin
from Tank.API.client import TankAPIClient


class DistributedPlugin(AbstractPlugin):
    SECTION = "distributed"

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        # config options
        self.retry_interval = 5
        self.running_tests = []
        self.tanks_count = 1
        self.configs = ["/dev/null"]
        self.options = []
        self.files = []
        self.artifacts_to_download = []
        self.chosen_tanks = []
        self.exclusive_mode = 1

        # regular fields
        self.api_clients = []
        self.api_client_class = TankAPIClient
        self.config_file = None
        self.start_time = None

    def get_available_options(self):
        return ["api_port", "api_timeout", "retry_interval",
                "tanks_pool", "tanks_count", "random_tanks", "exclusive_mode"
                                                             "configs", "options", "files", "download_artifacts"]

    def configure(self):
        self.retry_interval = int(self.get_option("retry_interval", self.retry_interval))
        api_timeout = int(self.get_option("api_timeout", 5))
        self.exclusive_mode = int(self.get_option("exclusive_mode", self.exclusive_mode))

        tanks_pool = self.get_multiline_option("tanks_pool")
        count = self.get_option("tanks_count", self.tanks_count)
        if count == 'all':
            self.tanks_count = len(tanks_pool)
        else:
            self.tanks_count = int(count)
            if self.tanks_count < len(tanks_pool):
                msg = "Misconfigured: tanks_count(%s) cannot be less than tanks_pool size(%s)"
                raise ValueError(msg % (self.tanks_count, len(tanks_pool)))

        random_tanks = int(self.get_option("random_tanks", 0))
        if random_tanks:
            random.shuffle(tanks_pool)

        self.configs = self.get_multiline_option("configs", self.configs)
        self.options = self.get_multiline_option("options", self.options)
        self.files = self.get_multiline_option("files", self.files)
        self.artifacts_to_download = self.get_multiline_option("download_artifacts", self.artifacts_to_download)

        # done reading options, do some preparations

        for tank in tanks_pool:
            self.api_clients.append(self.api_client_class(tank, api_timeout))

        self.config_file = self.__compose_load_ini(self.configs, self.options)
        self.core.add_artifact_file(self.config_file)

    def prepare_test(self):
        """ choosing tanks, uploading files, calling configure and prepare """
        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = DistributedInfoWidget(self)
            console.add_info_widget(widget)

        self.__choose_tanks()
        self.__prepare_tanks()

    def start_test(self):
        """ starting test  """
        for tank in self.chosen_tanks:
            tank.start_test()
            self.running_tests.append(tank)

    def is_test_finished(self):
        """ polling for the status of remote jobs """
        retcode = AbstractPlugin.is_test_finished(self)
        new_running = []
        for tank in self.running_tests:
            status = tank.get_test_status()
            if status["status"] == TankAPIClient.STATUS_RUNNING:
                new_running.append(tank)
            else:
                self.log.info("Tank has finished the test: %s", tank.address)

        self.running_tests = new_running

        if not self.running_tests:
            retcode = 0

        return retcode

    def end_test(self, retcode):
        """ call graceful shutdown for all tests """
        self.log.info("Shutting down remote tests...")
        for tank in self.chosen_tanks:
            try:
                tank.interrupt()
            except Exception, exc:
                self.log.warn("Exception while interrupting %s: %s", tank.address, exc)
                self.log.info("Retrying after %ss...", self.retry_interval)
                time.sleep(self.retry_interval)
                try:
                    tank.interrupt()
                except Exception, exc:
                    self.log.warn("Fatal exception while interrupting %s: %s", tank.address, traceback.format_exc(exc))

        for tank in self.chosen_tanks:
            try:
                while tank.get_test_status()["status"] != TankAPIClient.STATUS_FINISHED:
                    self.log.info("Waiting for test shutdown on %s...", tank.address)
                    time.sleep(self.retry_interval)
            except Exception, exc:
                self.log.warn("Exception while waiting %s: %s", tank.address, traceback.format_exc(exc))

    def post_process(self, retcode):
        """ download artifacts """
        if self.artifacts_to_download:
            for tank in self.chosen_tanks:
                self.__download_artifacts(tank)
        # TODO: change retcode if remote codes are not zero
        return retcode

    @staticmethod
    def get_key():
        return __file__

    def __compose_load_ini(self, configs, options):
        fname = self.core.mkstemp('.ini', 'load_')
        self.log.debug("Composing config: %s", fname)
        with open(fname, "w") as fd:
            for cfile in configs:
                fd.write("# === %s ===\n" % cfile)
                with open(cfile) as orig:
                    fd.write(orig.read())
                fd.write("\n\n")

            if options:
                self.log.debug("Merging additional options: %s", options)
                fd.write("\n\n#Command-line options added below\n")

                for option_str in options:
                    try:
                        section = option_str[:option_str.index('.')]
                        option = option_str[option_str.index('.') + 1:option_str.index('=')]
                    except ValueError:
                        section = 'DEFAULT'
                        option = option_str[:option_str.index('=')]
                    value = option_str[option_str.index('=') + 1:]
                    self.log.debug("Append option: %s => [%s] %s=%s", option_str, section, option, value)
                    fd.write("[%s]\n%s=%s\n" % (section, option, value))

        return fname

    def __choose_tanks(self):
        self.log.info("Choosing %s tanks from pool: %s", self.tanks_count, [t.address for t in self.api_clients])
        while len(self.chosen_tanks) < self.tanks_count:
            self.chosen_tanks = []
            for tank in self.api_clients:
                try:
                    if len(self.chosen_tanks) < self.tanks_count and tank.initiate_test(self.exclusive_mode):
                        self.chosen_tanks.append(tank)
                except Exception, exc:
                    self.log.info("Tank %s is unavailable: %s", tank.address, exc)
                    self.log.debug("Full exception: %s", traceback.format_exc(exc))

            if len(self.chosen_tanks) < self.tanks_count:
                self.log.info("Not enough tanks available (%s), waiting %ss before retry...",
                              len(self.chosen_tanks), self.retry_interval)
                self.log.debug("Releasing booked tanks")
                for tank in self.chosen_tanks:
                    tank.interrupt()
                time.sleep(self.retry_interval)

    def __prepare_tanks(self):
        self.log.info("Preparing chosen tanks: %s", [t.address for t in self.chosen_tanks])
        for tank in self.chosen_tanks:
            tank.prepare_test(self.config_file, self.files)
        self.log.debug("Waiting for tanks to be prepared...")
        pending_tanks = [tank for tank in self.chosen_tanks]
        while len(pending_tanks):
            self.log.debug("Waiting tanks: %s", pending_tanks)
            new_pending = []
            for tank in pending_tanks:
                status = tank.get_test_status()
                if status["status"] == TankAPIClient.STATUS_PREPARING:
                    new_pending.append(tank)
                elif status["status"] != TankAPIClient.STATUS_PREPARED:
                    raise RuntimeError("Failed to prepare test on %s: %s" %(tank.address, status["last_error"]))

            pending_tanks = new_pending
            if len(pending_tanks):
                self.log.info("Waiting tanks: %s", [t.address for t in pending_tanks])
                time.sleep(self.retry_interval)
        self.log.debug("Done waiting preparations")

    def __download_artifacts(self, tank):
        artifacts = tank.get_test_status()["artifacts"]
        for fname in self.artifacts_to_download:
            for artifact in artifacts:
                if fnmatch.fnmatch(artifact, fname):
                    self.log.info("Downloading artifact from %s: %s...", tank.address, artifact)
                    local_name = self.core.artifacts_base_dir + os.path.sep + artifact
                    tank.download_artifact(artifact, local_name)
                    self.core.add_artifact_file(local_name)


class DistributedInfoWidget(AbstractInfoWidget):
    def __init__(self, owner):
        AbstractInfoWidget.__init__(self)
        self.owner = owner
        self.krutilka = ConsoleScreen.krutilka()

    def get_index(self):
        return 0

    def aggregate_second(self, second_aggregate_data):
        #self.active_threads = second_aggregate_data.overall.active_threads
        #self.rps = second_aggregate_data.overall.rps
        #TODO: use the data
        pass

    def render(self, screen):
        pbar = " Distributed Test %s" % self.krutilka.next()
        space = screen.right_panel_width - len(pbar) - 1
        left_spaces = space / 2
        right_spaces = space / 2

        data = []
        template = screen.markup.BG_DARKGRAY + ':' * left_spaces + pbar + ' '
        template += ':' * right_spaces + screen.markup.RESET + "\n"
        #TODO: add relevant data
        #template += "     Test Plan: %s\n"
        if self.owner.start_time:
            dur_seconds = int(time.time()) - int(self.owner.start_time)
            duration = str(datetime.timedelta(seconds=dur_seconds))
            data.append(duration)

            template += "      Duration: %s\n"
        #template += "Active Threads: %s\n"
        #template += "   Responses/s: %s"

        return template % data
