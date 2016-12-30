# -*- coding: utf-8 -*-
""" Provides class to run TankCore from python """
import logging
import os
import sys
import time
import traceback
import fnmatch
from pkg_resources import resource_filename

from ..core import tankcore


class ApiWorker:
    """    Worker class that runs tank core via python   """

    def __init__(self):
        self.core = tankcore.TankCore()
        self.baseconfigs_location = '/etc/yandex-tank'
        self.log = logging.getLogger(__name__)

    def init_logging(self, log_filename="tank.log"):
        """ Set up logging """
        logger = logging.getLogger('')
        self.log_filename = log_filename
        self.core.add_artifact_file(self.log_filename)

        file_handler = logging.FileHandler(self.log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s %(message)s"))
        logger.addHandler(file_handler)
        console_handler = logging.StreamHandler(sys.stdout)
        stderr_hdl = logging.StreamHandler(sys.stderr)

        # fmt_verbose = logging.Formatter(
        #     "%(asctime)s [%(levelname)s] %(name)s %(message)s")
        fmt_regular = logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s", "%H:%M:%S")

        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(fmt_regular)
        stderr_hdl.setFormatter(fmt_regular)

        f_err = SingleLevelFilter(logging.ERROR, True)
        f_warn = SingleLevelFilter(logging.WARNING, True)
        f_crit = SingleLevelFilter(logging.CRITICAL, True)
        console_handler.addFilter(f_err)
        console_handler.addFilter(f_warn)
        console_handler.addFilter(f_crit)
        logger.addHandler(console_handler)

        f_info = SingleLevelFilter(logging.INFO, True)
        f_debug = SingleLevelFilter(logging.DEBUG, True)
        stderr_hdl.addFilter(f_info)
        stderr_hdl.addFilter(f_debug)
        logger.addHandler(stderr_hdl)

    def __add_user_options(self):
        """ override config options with user specified options"""
        if self.options.get('user_options', None):
            self.core.apply_shorthand_options(self.options['user_options'])

    def configure(self, options):
        """ Make preparations before running Tank """
        self.options = options
        if self.options.get('lock_dir', None):
            self.core.set_option(
                self.core.SECTION, "lock_dir", self.options['lock_dir'])

        while True:
            try:
                self.core.get_lock(self.options.get('ignore_lock', None))
                break
            except Exception as exc:
                if self.options.get('lock_fail', None):
                    raise RuntimeError("Lock file present, cannot continue")
                self.log.info(
                    "Couldn't get lock. Will retry in 5 seconds... (%s)",
                    str(exc))
                time.sleep(5)

        configs = self.get_default_configs()
        if self.options.get('config', None):
            configs.append(self.options['config'])
        self.core.load_configs(configs)
        self.__add_user_options()
        self.core.load_plugins()

        if self.options.get('ignore_lock', None):
            self.core.set_option(self.core.SECTION, self.IGNORE_LOCKS, "1")

    def perform_test(self):
        """ Run the test and wait for finish """
        self.log.info("Performing test...")
        retcode = 1
        try:
            self.core.plugins_configure()
            self.core.plugins_prepare_test()
            if self.options.get('manual_start', None):
                self.log.info(
                    "Manual start option specified, waiting for user actions")
                raw_input("Press Enter key to start test")

            self.core.plugins_start_test()
            retcode = self.core.wait_for_finish()
            retcode = self.core.plugins_end_test(retcode)
            retcode = self.core.plugins_post_process(retcode)
        except KeyboardInterrupt as ex:
            self.log.info(
                "Do not press Ctrl+C again, the test will be broken otherwise")
            self.log.debug(
                "Caught KeyboardInterrupt: %s", traceback.format_exc(ex))
            try:
                retcode = self.__graceful_shutdown()
            except KeyboardInterrupt as ex:
                self.log.debug(
                    "Caught KeyboardInterrupt again: %s",
                    traceback.format_exc(ex))
                self.log.info(
                    "User insists on exiting, aborting graceful shutdown...")
                retcode = 1

        except Exception as ex:
            self.log.info("Exception: %s", traceback.format_exc(ex))
            self.log.error("%s", ex)
            retcode = self.__graceful_shutdown()
            self.core.release_lock()

        self.log.info("Done performing test with code %s", retcode)
        return retcode

    def get_default_configs(self):
        """ returns default configs list, from /etc, home dir and package_data"""
        # initialize basic defaults
        configs = [resource_filename(__name__, 'config/00-base.ini')]
        try:
            conf_files = sorted(os.listdir(self.baseconfigs_location))
            for filename in conf_files:
                if fnmatch.fnmatch(filename, '*.ini'):
                    configs += [
                        os.path.realpath(
                            self.baseconfigs_location + os.sep + filename)
                    ]
        except OSError:
            self.log.warn(
                self.baseconfigs_location +
                ' is not accessible to get configs list')

        configs += [os.path.expanduser('~/.yandex-tank')]
        return configs

    def __graceful_shutdown(self):
        """ call shutdown routines """
        retcode = 1
        self.log.info("Trying to shutdown gracefully...")
        retcode = self.core.plugins_end_test(retcode)
        retcode = self.core.plugins_post_process(retcode)
        self.log.info("Done graceful shutdown")
        return retcode


class SingleLevelFilter(logging.Filter):
    """Exclude or approve one msg type at a time.    """

    def __init__(self, passlevel, reject):
        logging.Filter.__init__(self)
        self.passlevel = passlevel
        self.reject = reject

    def filter(self, record):
        if self.reject:
            return record.levelno != self.passlevel
        else:
            return record.levelno == self.passlevel
