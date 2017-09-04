# coding=utf-8
# TODO: make the next two lines unnecessary
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import logging
import os
import pwd
import re
import sys
import time
from future.moves.urllib.parse import urljoin

from queue import Empty, Queue
from builtins import str
import requests
import threading

from ...common.interfaces import AbstractPlugin, \
    MonitoringDataListener, AggregateResultListener, AbstractInfoWidget
from ...common.util import expand_to_seconds
from ..Autostop import Plugin as AutostopPlugin
from ..Console import Plugin as ConsolePlugin
from .client import APIClient, OverloadClient

logger = logging.getLogger(__name__)  # pylint: disable=C0103


class BackendTypes(object):
    OVERLOAD = 'OVERLOAD'
    LUNAPARK = 'LUNAPARK'

    @classmethod
    def identify_backend(cls, api_address):
        clues = [
            ('overload', cls.OVERLOAD),
            ('lunapark', cls.LUNAPARK),
        ]
        for clue, backend_type in clues:
            if clue in api_address:
                return backend_type
        else:
            raise KeyError('Config section name doesn\'t match any of the patterns:\n%s' %
                           '\n'.join(['*%s*' % ptrn[0] for ptrn in clues]))
        pass


def chop(data_list, chunk_size):
    if sys.getsizeof(str(data_list)) <= chunk_size:
        return [data_list]
    elif len(data_list) == 1:
        logger.warning("Too large piece of Telegraf data. Might experience upload problems.")
        return [data_list]
    else:
        mid = len(data_list) / 2
        return chop(data_list[:mid], chunk_size) + chop(data_list[mid:], chunk_size)


class Plugin(AbstractPlugin, AggregateResultListener,
             MonitoringDataListener):
    RC_STOP_FROM_WEB = 8
    VERSION = '3.0'
    SECTION = 'uploader'

    def __init__(self, core, cfg, cfg_updater):
        AbstractPlugin.__init__(self, core, cfg, cfg_updater)
        self.data_queue = Queue()
        self.monitoring_queue = Queue()
        self.retcode = -1
        self._target = None
        self.task_name = ''
        self.token_file = None
        self.version_tested = None
        self.send_status_period = 10

        self.status_sender = threading.Thread(target=self.__send_status)
        self.status_sender.daemon = True

        self.upload = threading.Thread(target=self.__data_uploader)
        self.upload.daemon = True

        self.monitoring = threading.Thread(target=self.__monitoring_uploader)
        self.monitoring.daemon = True

        self._generator_info = None
        self._is_telegraf = None
        self.backend_type = BackendTypes.identify_backend(self.cfg['api_address'])
        self._task = None
        self._api_token = ''
        self._lp_job = None
        self._lock_duration = None
        self._info = None
        self.locked_targets = []

    @staticmethod
    def get_key():
        return __file__

    @property
    def lock_duration(self):
        if self._lock_duration is None:
            self._lock_duration = self.generator_info.duration if self.generator_info.duration else \
                expand_to_seconds(self.get_option("target_lock_duration"))
        return self._lock_duration

    def get_available_options(self):
        opts = [
            "api_address",
            "writer_endpoint",
            "task",
            "job_name",
            "job_dsc",
            "notify",
            "ver", "component",
            "regress",
            "operator",
            "jobno_file",
            "ignore_target_lock",
            "target_lock_duration",
            "lock_targets",
            "jobno",
            "upload_token",
            'connection_timeout',
            'network_attempts',
            'api_attempts',
            'maintenance_attempts',
            'network_timeout',
            'api_timeout',
            'maintenance_timeout',
            'strict_lock',
            'send_status_period',
            'log_data_requests',
            'log_monitoring_requests',
            'log_status_requests',
            'log_other_requests',
            'threads_timeout',
            'chunk_size'
        ]
        return opts

    def configure(self):
        pass

    def check_task_is_open(self):
        if self.backend_type == BackendTypes.OVERLOAD:
            return
        TASK_TIP = 'The task should be connected to Lunapark. Open startrek task page, click "actions" -> "load testing".'

        logger.debug("Check if task %s is open", self.task)
        try:
            task_data = self.lp_job.get_task_data(self.task)[0]
            try:
                task_status = task_data['status']
                if task_status == 'Open':
                    logger.info("Task %s is ok", self.task)
                    self.task_name = str(task_data['name'])
                else:
                    logger.info("Task %s:" % self.task)
                    logger.info(task_data)
                    raise RuntimeError("Task is not open")
            except KeyError:
                try:
                    error = task_data['error']
                    raise RuntimeError(
                        "Task %s error: %s\n%s" %
                        (self.task, error, TASK_TIP))
                except KeyError:
                    raise RuntimeError(
                        'Unknown task data format:\n{}'.format(task_data))
        except requests.exceptions.HTTPError as ex:
            logger.error("Failed to check task status for '%s': %s", self.task, ex)
            if ex.response.status_code == 404:
                raise RuntimeError("Task not found: %s\n%s" % (self.task, TASK_TIP))
            elif ex.response.status_code == 500 or ex.response.status_code == 400:
                raise RuntimeError(
                    "Unable to check task staus, id: %s, error code: %s" %
                    (self.task, ex.response.status_code))
            raise ex

    @staticmethod
    def search_task_from_cwd(cwd):
        issue = re.compile("^([A-Za-z]+-[0-9]+)(-.*)?")
        while cwd:
            logger.debug("Checking if dir is named like JIRA issue: %s", cwd)
            if issue.match(os.path.basename(cwd)):
                res = re.search(issue, os.path.basename(cwd))
                return res.group(1).upper()

            newdir = os.path.abspath(os.path.join(cwd, os.path.pardir))
            if newdir == cwd:
                break
            else:
                cwd = newdir

        raise RuntimeError(
            "task=dir requested, but no JIRA issue name in cwd: %s" %
            os.getcwd())

    def prepare_test(self):
        info = self.generator_info
        port = info.port
        instances = info.instances
        if info.ammo_file.startswith(
                "http://") or info.ammo_file.startswith("https://"):
            ammo_path = info.ammo_file
        else:
            ammo_path = os.path.realpath(info.ammo_file)
        loop_count = info.loop_count

        try:
            lp_job = self.lp_job
            self.locked_targets = self.check_and_lock_targets(strict=self.get_option('strict_lock'),
                                                              ignore=self.get_option('ignore_target_lock'))
            if lp_job._number:
                self.make_symlink(lp_job._number)
                self.check_task_is_open()
            else:
                self.check_task_is_open()
                lp_job.create()
                self.make_symlink(lp_job.number)
            self.publish('job_no', lp_job.number)
        except (APIClient.JobNotCreated, APIClient.NotAvailable, APIClient.NetworkError) as e:
            logger.error(e.message)
            logger.error(
                'Failed to connect to Lunapark, disabling DataUploader')
            self.start_test = lambda *a, **kw: None
            self.post_process = lambda *a, **kw: None
            self.on_aggregated_data = lambda *a, **kw: None
            self.monitoring_data = lambda *a, **kw: None
            return

        cmdline = ' '.join(sys.argv)
        lp_job.edit_metainfo(
            instances=instances,
            ammo_path=ammo_path,
            loop_count=loop_count,
            is_regression=self.get_option(
                'regress',
                '0'),
            regression_component=self.get_option("component"),
            cmdline=cmdline,
        )  # todo: tanktype?

        self.core.job.subscribe_plugin(self)

        try:
            console = self.core.get_plugin_of_type(ConsolePlugin)
        except KeyError:
            logger.debug("Console plugin not found", exc_info=True)
            console = None

        if console:
            console.add_info_widget(JobInfoWidget(self))

        self.set_option('target_host', self.target)
        self.set_option('target_port', port)
        self.set_option('cmdline', cmdline)
        self.set_option('ammo_path', ammo_path)
        self.set_option('loop_count', loop_count)
        self.__save_conf()

    def start_test(self):
        self.on_air = True

        self.status_sender.start()
        self.upload.start()
        self.monitoring.start()

        web_link = urljoin(self.lp_job.api_client.base_url, str(self.lp_job.number))
        logger.info("Web link: %s", web_link)

        self.publish("jobno", self.lp_job.number)
        self.publish("web_link", web_link)

        jobno_file = self.get_option("jobno_file", '')
        if jobno_file:
            logger.debug("Saving jobno to: %s", jobno_file)
            with open(jobno_file, 'w') as fdes:
                fdes.write(str(self.lp_job.number))
        self.__save_conf()

    def is_test_finished(self):
        return self.retcode

    def end_test(self, retcode):
        self.on_air = False
        self.monitoring_queue.put(None)
        self.data_queue.put(None)
        self.__save_conf()
        self._join_threads(timeout=int(self.get_option('threads_timeout')))
        self.unlock_targets(self.locked_targets)
        return retcode

    def post_process(self, rc):
        try:
            self.lp_job.close(rc)
        except Exception:  # pylint: disable=W0703
            logger.warning("Failed to close job", exc_info=True)

        logger.info(
            "Web link: %s%s",
            self.lp_job.api_client.base_url,
            self.lp_job.number)

        autostop = None
        try:
            autostop = self.core.get_plugin_of_type(AutostopPlugin)
        except KeyError:
            logger.debug("No autostop plugin loaded", exc_info=True)

        if autostop and autostop.cause_criterion:
            rps = 0
            if autostop.cause_criterion.cause_second:
                rps = autostop.cause_criterion.cause_second[
                    1]["metrics"]["reqps"]
                if not rps:
                    rps = autostop.cause_criterion.cause_second[0][
                        "overall"]["interval_real"]["len"]
            self.lp_job.set_imbalance_and_dsc(
                int(rps), autostop.cause_criterion.explain())

        else:
            logger.debug("No autostop cause detected")
        self.__save_conf()
        return rc

    def on_aggregated_data(self, data, stats):
        """
        @data: aggregated data
        @stats: stats about gun
        """
        if self.lp_job.is_alive:
            self.data_queue.put((data, stats))

    def monitoring_data(self, data_list):
        if self.lp_job.is_alive:
            if len(data_list) > 0:
                if self.is_telegraf:
                    # telegraf
                    [self.monitoring_queue.put(chunk) for chunk in chop(data_list, self.get_option("chunk_size"))]
                else:
                    # monitoring
                    [self.monitoring_queue.put(data) for data in data_list]

    @property
    def is_telegraf(self):
        if self._is_telegraf is None:
            self._is_telegraf = 'Telegraf' in self.core.job.monitoring_plugin.__module__
        return self._is_telegraf

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
        logger.debug("We are%s running under API server", '' if api_found else ' likely not')
        return api_found

    def __send_status(self):
        logger.info('Status sender thread started')
        lp_job = self.lp_job
        while lp_job.is_alive and self.on_air:
            try:
                self.lp_job.send_status(self.core.status)
                time.sleep(self.get_option('send_status_period'))
            except (APIClient.NetworkError, APIClient.NotAvailable) as e:
                logger.warn('Failed to send status')
                logger.debug(e.message)
                break
            except APIClient.StoppedFromOnline:
                logger.info("Test stopped from Lunapark")
                lp_job.is_alive = False
                self.retcode = 8
                break
        logger.info("Closing Status sender thread")

    def __data_uploader(self):
        logger.info('Data uploader thread started')
        lp_job = self.lp_job
        queue = self.data_queue
        while lp_job.is_alive:
            try:
                entry = queue.get(timeout=1)
                if entry is not None:
                    data, stats = entry
                else:
                    logger.info("Data uploader queue returned None")
                    break
                lp_job.push_test_data(data, stats)
            except Empty:
                continue
            except APIClient.StoppedFromOnline:
                logger.info("Test stopped from Lunapark")
                lp_job.is_alive = False
                self.retcode = 8
                break
            except Exception as e:
                logger.info("Mysterious exception: %s", e)
                self.retcode = 8
                break
        logger.info("Closing Data uploader thread")

    def __monitoring_uploader(self):
        logger.info('Monitoring uploader thread started')
        lp_job = self.lp_job
        queue = self.monitoring_queue
        while lp_job.is_alive:
            try:
                data = queue.get(timeout=1)
                if data is not None:
                    lp_job.push_monitoring_data(data)
                else:
                    logger.info('Monitoring queue returned None')
                    break
            except Empty:
                continue
            except (APIClient.NetworkError, APIClient.NotAvailable, APIClient.UnderMaintenance) as e:
                logger.warn('Failed to push monitoring data')
                logger.warn(e.message)
                break
            except APIClient.StoppedFromOnline:
                logger.info("Test stopped from Lunapark")
                lp_job.is_alive = False
                self.retcode = 8
                break
        logger.info('Closing Monitoring uploader thread')

    # TODO: why we do it here? should be in core
    def __save_conf(self):
        # config = copy.deepcopy(self.core.config)
        try:
            config_filename = self.core.job.monitoring_plugin.config
            if config_filename and config_filename not in ['none', 'auto']:
                with open(config_filename) as config_file:
                    self.core.job.monitoring_plugin.set_option("config_contents",
                                                               config_file.read())
        except AttributeError:  # pylint: disable=W0703
            logger.warning("Can't get monitoring config", exc_info=True)

        self.lp_job.send_config_snapshot(self.core.cfg_snapshot)
        self.core.config.save(os.path.join(self.core.artifacts_dir, 'saved_conf.yaml'))

    def parse_lock_targets(self):
        # prepare target lock list
        locks_list_cfg = self.get_option('lock_targets', 'auto').strip()

        def no_target():
            logging.warn("Target lock set to 'auto', but no target info available")
            return ''

        locks_list = (self.target or no_target() if locks_list_cfg.lower() == 'auto' else locks_list_cfg).split('\n')
        targets_to_lock = [host for host in locks_list if host]
        return targets_to_lock

    def lock_targets(self, targets_to_lock, ignore, strict):
        locked_targets = [target for target in targets_to_lock
                          if self.lp_job.lock_target(target, self.lock_duration, ignore, strict)]
        return locked_targets

    def unlock_targets(self, locked_targets):
        logger.info("Unlocking targets: %s", locked_targets)
        for target in locked_targets:
            logger.info(target)
            self.lp_job.api_client.unlock_target(target)

    def check_and_lock_targets(self, strict, ignore):
        targets_list = self.parse_lock_targets()
        logger.info('Locking targets: %s', targets_list)
        locked_targets = self.lock_targets(targets_list, ignore=ignore, strict=strict)
        logger.info('Locked targets: %s', locked_targets)
        return locked_targets

    def make_symlink(self, name):
        PLUGIN_DIR = os.path.join(self.core.artifacts_base_dir, 'lunapark')
        if not os.path.exists(PLUGIN_DIR):
            os.makedirs(PLUGIN_DIR)
        os.symlink(
            os.path.relpath(
                self.core.artifacts_dir,
                PLUGIN_DIR),
            os.path.join(
                PLUGIN_DIR,
                str(name)))

    def _get_user_agent(self):
        plugin_agent = 'Uploader/{}'.format(self.VERSION)
        return ' '.join((plugin_agent,
                         self.core.get_user_agent()))

    def __get_operator(self):
        try:
            return self.get_option(
                'operator') or pwd.getpwuid(
                os.geteuid())[0]
        except:
            logger.error(
                "Couldn't get username from the OS. Please, set the 'meta.operator' option explicitly in your config file.")
            raise

    def __get_api_client(self):
        if self.backend_type == BackendTypes.LUNAPARK:
            client = APIClient
            self._api_token = None
        elif self.backend_type == BackendTypes.OVERLOAD:
            client = OverloadClient
            self._api_token = self.read_token(self.get_option("token_file"))
        else:
            raise RuntimeError("Backend type doesn't match any of the expected")

        return client(base_url=self.get_option('api_address'),
                      writer_url=self.get_option('writer_endpoint'),
                      network_attempts=self.get_option('network_attempts'),
                      api_attempts=self.get_option('api_attempts'),
                      maintenance_attempts=self.get_option('maintenance_attempts'),
                      network_timeout=self.get_option('network_timeout'),
                      api_timeout=self.get_option('api_timeout'),
                      maintenance_timeout=self.get_option('maintenance_timeout'),
                      connection_timeout=self.get_option('connection_timeout'),
                      user_agent=self._get_user_agent(),
                      api_token=self.api_token)

    @property
    def lp_job(self):
        """

        :rtype: LPJob
        """
        if self._lp_job is None:
            self._lp_job = self.__get_lp_job()
            self.core.publish(self.SECTION, 'job_no', self._lp_job.number)
            self.core.publish(self.SECTION, 'web_link', self._lp_job.web_link)
            self.set_option("jobno", self.lp_job.number)
            self.core.write_cfg_to_lock()
        return self._lp_job

    def __get_lp_job(self):
        """

        :rtype: LPJob
        """
        api_client = self.__get_api_client()

        info = self.generator_info
        port = info.port
        loadscheme = [] if isinstance(info.rps_schedule,
                                      str) else info.rps_schedule

        return LPJob(client=api_client,
                     target_host=self.target,
                     target_port=port,
                     number=self.cfg.get('jobno', None),
                     token=self.get_option('upload_token'),
                     person=self.__get_operator(),
                     task=self.task,
                     name=self.get_option('job_name', 'none').decode('utf8'),
                     description=self.get_option('job_dsc').decode('utf8'),
                     tank=self.core.job.tank,
                     notify_list=self.get_option("notify", '').split(' '),
                     load_scheme=loadscheme,
                     version=self.get_option('ver'),
                     log_data_requests=self.get_option('log_data_requests'),
                     log_monitoring_requests=self.get_option('log_monitoring_requests'),
                     log_status_requests=self.get_option('log_status_requests'),
                     log_other_requests=self.get_option('log_other_requests'))

    @property
    def task(self):
        if self._task is None:
            task = self.get_option('task')
            if task == 'dir':
                task = self.search_task_from_cwd(os.getcwd())
            self._task = task
        return self._task

    @property
    def api_token(self):
        if self._api_token == '':
            if self.backend_type == BackendTypes.LUNAPARK:
                self._api_token = None
            elif self.backend_type == BackendTypes.OVERLOAD:
                self._api_token = self.read_token(self.get_option("token_file", ""))
            else:
                raise RuntimeError("Backend type doesn't match any of the expected")
        return self._api_token

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

    @property
    def generator_info(self):
        if self._generator_info is None:
            self._generator_info = self.core.job.generator_plugin.get_info()
        return self._generator_info

    @property
    def target(self):
        if self._target is None:
            self._target = self.generator_info.address
            logger.info("Detected target: %s", self.target)
        return self._target

    def _join_threads(self, timeout):
        logger.info(
            'Waiting for sender threads to join for {} seconds ("meta.threads_timeout" config option)'.format(timeout))
        try:
            self.monitoring.join(timeout=timeout)
            if self.monitoring.isAlive():
                logger.error('Monitoring thread joining timed out. Terminating.')
        except RuntimeError:
            pass
        try:
            self.upload.join(timeout=timeout)
            if self.upload.isAlive():
                logger.error('Upload thread joining timed out. Terminating.')
        except RuntimeError:
            pass


class JobInfoWidget(AbstractInfoWidget):
    def __init__(self, sender):
        # type: (Plugin) -> object
        AbstractInfoWidget.__init__(self)
        self.owner = sender

    def get_index(self):
        return 1

    def render(self, screen):
        template = "Author: " + screen.markup.RED + "%s" + \
                   screen.markup.RESET + \
                   "%s\n   Job: %s %s\n  Task: %s %s\n   Web: %s%s"
        data = (self.owner.lp_job.person[:1], self.owner.lp_job.person[1:],
                self.owner.lp_job.number, self.owner.lp_job.name, self.owner.lp_job.task,
                # todo: task_name from api_client.get_task_data()
                self.owner.lp_job.task, self.owner.lp_job.api_client.base_url,
                self.owner.lp_job.number)

        return template % data


class LPJob(object):
    def __init__(
            self,
            client,
            target_host,
            target_port,
            person,
            task,
            name,
            description,
            tank,
            log_data_requests=False,
            log_other_requests=False,
            log_status_requests=False,
            log_monitoring_requests=False,
            number=None,
            token=None,
            is_alive=True,
            notify_list=None,
            version=None,
            detailed_time=None,
            load_scheme=None):
        """
        :param client: APIClient
        :param log_data_requests: bool
        :param log_other_request: bool
        :param log_status_requests: bool
        :param log_monitoring_requests: bool
        """
        assert bool(number) == bool(
            token), 'Job number and upload token should come together'
        self.log_other_requests = log_other_requests
        self.log_data_requests = log_data_requests
        self.log_status_requests = log_status_requests
        self.log_monitoring_requests = log_monitoring_requests
        self.name = name
        self.tank = tank
        self.target_host = target_host
        self.target_port = target_port
        self.person = person
        self.task = task
        self.is_alive = is_alive
        self._number = number
        self._token = token
        self.api_client = client
        self.notify_list = notify_list
        self.description = description
        self.version = version
        self.detailed_time = detailed_time
        self.load_scheme = load_scheme
        self.is_finished = False
        self.web_link = ''

    def push_test_data(self, data, stats):
        if self.is_alive:
            try:
                self.api_client.push_test_data(
                    self.number, self.token, data, stats, trace=self.log_data_requests)
            except (APIClient.NotAvailable, APIClient.NetworkError, APIClient.UnderMaintenance):
                logger.warn('Failed to push test data')
                self.is_alive = False

    def edit_metainfo(
            self,
            instances=0,
            ammo_path=None,
            loop_count=None,
            is_regression=None,
            regression_component=None,
            cmdline=None,
            is_starred=False,
            tank_type=1):
        try:
            self.api_client.edit_job_metainfo(jobno=self.number,
                                              job_name=self.name,
                                              job_dsc=self.description,
                                              instances=instances,
                                              ammo_path=ammo_path,
                                              loop_count=loop_count,
                                              version_tested=self.version,
                                              is_regression=is_regression,
                                              component=regression_component,
                                              cmdline=cmdline,
                                              is_starred=is_starred,
                                              tank_type=tank_type,
                                              trace=self.log_other_requests)
        except (APIClient.NotAvailable, APIClient.StoppedFromOnline, APIClient.NetworkError,
                APIClient.UnderMaintenance) as e:
            logger.warn('Failed to edit job metainfo on Lunapark')
            logger.warn(e.message)

    @property
    def number(self):
        if not self._number:
            self.create()
        return self._number

    @property
    def token(self):
        if not self._token:
            self.create()
        return self._token

    def close(self, rc):
        if self._number:
            return self.api_client.close_job(self.number, rc, trace=self.log_other_requests)
        else:
            return True

    def create(self):
        self._number, self._token = self.api_client.new_job(task=self.task,
                                                            person=self.person,
                                                            tank=self.tank,
                                                            loadscheme=self.load_scheme,
                                                            target_host=self.target_host,
                                                            target_port=self.target_port,
                                                            detailed_time=self.detailed_time,
                                                            notify_list=self.notify_list,
                                                            trace=self.log_other_requests)
        logger.info('Job created: {}'.format(self._number))
        self.web_link = urljoin(self.api_client.base_url, str(self._number))

    def send_status(self, status):
        if self._number and self.is_alive:
            self.api_client.send_status(
                self.number,
                self.token,
                status,
                trace=self.log_status_requests)

    def get_task_data(self, task):
        return self.api_client.get_task_data(
            task, trace=self.log_other_requests)

    def send_config_snapshot(self, config):
        if self._number:
            self.api_client.send_config_snapshot(
                self.number, config, trace=self.log_other_requests)

    def push_monitoring_data(self, data):
        if self.is_alive:
            self.api_client.push_monitoring_data(
                self.number, self.token, data, trace=self.log_monitoring_requests)

    def lock_target(self, lock_target, lock_target_duration, ignore, strict):
        lock_wait_timeout = 10
        maintenance_timeouts = iter([0]) if ignore else iter(lambda: lock_wait_timeout, 0)
        while True:
            try:
                self.api_client.lock_target(lock_target, lock_target_duration, trace=self.log_other_requests,
                                            maintenance_timeouts=maintenance_timeouts,
                                            maintenance_msg="Target is locked.\nManual unlock link: %s%s" % (
                                                self.api_client.base_url,
                                                self.api_client.get_manual_unlock_link(lock_target)
                                            ))
                return True
            except (APIClient.NotAvailable, APIClient.StoppedFromOnline) as e:
                logger.info('Target is not locked due to %s', e.message)
                if ignore:
                    logger.info('ignore_target_locks = 1')
                    return False
                elif strict:
                    raise e
                else:
                    logger.info('strict_lock = 0')
                    return False
            except APIClient.UnderMaintenance:
                logger.info('Target is locked')
                if ignore:
                    logger.info('ignore_target_locks = 1')
                    return False
                logger.info("Manual unlock link: %s%s", self.api_client.base_url,
                            self.api_client.get_manual_unlock_link(lock_target))
                continue

    def set_imbalance_and_dsc(self, rps, comment):
        return self.api_client.set_imbalance_and_dsc(self.number, rps, comment)

    def is_target_locked(self, host, strict):
        while True:
            try:
                return self.api_client.is_target_locked(
                    host, trace=self.log_other_requests)
            except APIClient.UnderMaintenance:
                logger.info('Target is locked, retrying...')
                continue
            except (APIClient.StoppedFromOnline, APIClient.NotAvailable, APIClient.NetworkError):
                logger.warn('Can\'t check whether target is locked\n')
                if strict:
                    logger.warn('Stopping test due to strict_lock')
                    raise
                else:
                    logger.warn('strict_lock is False, proceeding')
                    return {'status': 'ok'}
