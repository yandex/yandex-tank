import logging


class AbstractPlugin(object):
    """ Plugin interface
    Parent class for all plugins """

    SECTION = 'DEFAULT'

    @staticmethod
    def get_key():
        """ Get dictionary key for plugin,
        should point to __file__ magic constant """
        raise TypeError("Abstract method needs to be overridden")

    # TODO: do we realy need cfg_updater here?
    def __init__(self, core, cfg, name):
        """

        :param name:
        :type core: yandextank.core.TankCore
        :type cfg: dict
        """
        super(AbstractPlugin, self).__init__()
        self._cleanup_actions = []
        self.log = logging.getLogger(__name__)
        self.core = core
        self.cfg = cfg
        self.cfg_section_name = name
        self.interrupted = self.core.interrupted

    def set_option(self, option, value):
        self.cfg[option] = value

    def configure(self):
        """ A stage to read config values and instantiate objects """
        pass

    def prepare_test(self):
        """        Test preparation tasks        """
        pass

    def start_test(self):
        """        Launch test process        """
        pass

    def is_test_finished(self):
        """
        Polling call, if result differs from -1 then test end
        will be triggered
        """
        return -1

    def add_cleanup(self, action):
        """
        :type action: function
        """
        assert callable(action)
        self._cleanup_actions.append(action)

    def cleanup(self):
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception:
                logging.error('Exception occurred during plugin cleanup {}'.format(self.__module__), exc_info=True)

    def end_test(self, retcode):
        """
        Stop processes launched at 'start_test',
        change return code if necessary
        """
        return retcode

    def post_process(self, retcode):
        """ Post-process test data """
        return retcode

    def get_option(self, option_name, default_value=None):
        """ Wrapper to get option from plugins' section """
        return self.cfg.get(option_name, default_value)

    def get_available_options(self):
        """ returns array containing known options for plugin """
        return []

    def get_multiline_option(self, option_name, default_value=None):
        if default_value is not None:
            default = ' '.join(default_value)
        else:
            default = None
        value = self.get_option(option_name, default)
        if value:
            return (' '.join(value.split("\n"))).split(' ')
        else:
            return ()

    def publish(self, key, value):
        """publish value to status"""
        self.log.debug(
            "Publishing status: %s/%s: %s", self.__class__.SECTION, key, value)
        self.core.publish(self.__class__.SECTION, key, value)

    def close(self):
        """
        Release allocated resources here.
        Warning: don't do any logic or potentially dangerous operations
        """
        pass


class MonitoringDataListener(object):
    """ Monitoring listener interface
    parent class for Monitoring data listeners"""

    def __init__(self):
        pass

    def monitoring_data(self, data):
        """Notification about new monitoring data lines"""
        raise NotImplementedError("Abstract method needs to be overridden")


class AggregateResultListener(object):
    """ Listener interface
    parent class for Aggregate results listeners"""

    def on_aggregated_data(self, data, stats):
        """
        notification about new aggregated data and stats

        data contains aggregated metrics and stats contain non-aggregated
        metrics from gun (like instances count, for example)

        data and stats are cached and synchronized by timestamp. Stat items
        are holded until corresponding data item is received and vice versa.
        """
        raise NotImplementedError("Abstract method should be overridden")


class AbstractInfoWidget(object):
    """ InfoWidgets interface
    parent class for all InfoWidgets"""

    def __init__(self):
        pass

    def render(self, screen):
        raise NotImplementedError("Abstract method should be overridden")

    def on_aggregated_data(self, data, stats):
        raise NotImplementedError("Abstract method should be overridden")

    def get_index(self):
        """ get vertical priority index """
        return 0


class AbstractCriterion(object):
    """ Criterions interface,
    parent class for all criterions """
    RC_TIME = 21
    RC_HTTP = 22
    RC_NET = 23
    RC_STEADY = 33

    def __init__(self):
        self.cause_second = None

    @staticmethod
    def count_matched_codes(codes_regex, codes_dict):
        """ helper to aggregate codes by mask """
        total = 0
        for code, count in codes_dict.items():
            if codes_regex.match(str(code)):
                total += count
        return total

    def notify(self, data, stat):
        """ notification about aggregate data goes here """
        raise NotImplementedError("Abstract methods requires overriding")

    def get_rc(self):
        """ get return code for test """
        raise NotImplementedError("Abstract methods requires overriding")

    def explain(self):
        """ long explanation to show after test stop """
        raise NotImplementedError("Abstract methods requires overriding")

    def get_criterion_parameters(self):
        """ returns dict with all criterion parameters """
        raise NotImplementedError("Abstract methods requires overriding")

    def widget_explain(self):
        """ short explanation to display in right panel """
        return self.explain(), 0

    @staticmethod
    def get_type_string():
        """ returns string that used as config name for criterion """
        raise NotImplementedError("Abstract methods requires overriding")


class GeneratorPlugin(AbstractPlugin):
    DEFAULT_INFO = {
        'address': '',
        'port': 80,
        'instances': 1,
        'ammo_file': '',
        'rps_schedule': [],
        'duration': 0,
        'loop_count': 0
    }

    def __init__(self, core, cfg, name):
        super(GeneratorPlugin, self).__init__(core, cfg, name)
        self.stats_reader = None
        self.reader = None
        self.process = None
        self.process_stderr = None
        self.start_time = None
        self.affinity = None
        self.buffered_seconds = 2

    class Info(object):
        def __init__(
                self, address, port, instances, ammo_file, rps_schedule,
                duration, loop_count):
            self.address = address
            self.port = port
            self.instances = instances
            self.ammo_file = ammo_file
            self.rps_schedule = rps_schedule
            self.duration = duration
            self.loop_count = loop_count

    def get_info(self):
        """
        :rtype: GeneratorPlugin.Info
        """
        return self.Info(**self.DEFAULT_INFO)

    def get_reader(self):
        """

        :rtype: collections.Iterable
        """
        pass

    def get_stats_reader(self):
        """

        :rtype: collections.Iterable
        """
        pass

    def end_test(self, retcode):
        pass


class StatsReader(object):
    @staticmethod
    def stats_item(ts, instances, rps):
        return {
            'ts': ts,
            'metrics': {
                'instances': instances,
                'reqps': rps
            }
        }


class MonitoringPlugin(AbstractPlugin):

    def __init__(self, core, cfg, name):
        super(MonitoringPlugin, self).__init__(core, cfg, name)
        self.listeners = set()

    def add_listener(self, plugin):
        self.listeners.add(plugin)


class TankInfo(object):
    def __init__(self, info):
        self._info = info

    def get_info_dict(self):
        return self._info.copy()

    def _set_info(self, new_info_dict):
        raise NotImplementedError

    def update(self, keys, value):
        if len(keys) > 1:
            self._info[keys[0]] = self._update_dict(self.get_value([keys[0]], {}), keys[1:], value)
        else:
            self._info[keys[0]] = value

    def get_value(self, keys, default=None):
        value = self.get_info_dict()
        for key in keys:
            value = value.get(key, {})
        return value or default

    @classmethod
    def _update_dict(cls, status_dict, keys, value):
        if len(keys) > 1:
            cls._update_dict(status_dict.setdefault(keys[0], {}), keys[1:], value)
        else:
            status_dict[keys[0]] = value
        return status_dict
