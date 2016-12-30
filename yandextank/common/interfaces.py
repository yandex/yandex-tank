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

    def __init__(self, core):
        """

        @type core: TankCore
        """
        self.log = logging.getLogger(__name__)
        self.core = core

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
        will be triggeted
        """
        return -1

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
        return self.core.get_option(self.SECTION, option_name, default_value)

    def set_option(self, option_name, value):
        """ Wrapper to set option to plugins' section """
        return self.core.set_option(self.SECTION, option_name, value)

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
            "Publishing status: %s/%s: %s", self.__class__.__name__, key, value)
        self.core.publish(self.__class__.__name__, key, value)

    def close(self):
        """
        Release allocated resources here.
        Warning: don't do any logic or potentially dangerous operations
        """
        pass


class MonitoringDataListener(object):
    """ Monitoring interface
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
        raise NotImplementedError("Abstract method needs to be overridden")


class AbstractInfoWidget(object):
    ''' InfoWidgets interface
    parent class for all InfoWidgets'''

    def __init__(self):
        pass

    def render(self, screen):
        raise NotImplementedError("Abstract method needs to be overridden")

    def get_index(self):
        ''' get vertical priority index '''
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

    def widget_explain(self):
        """ short explanation to display in right panel """
        return self.explain(), 0

    @staticmethod
    def get_type_string():
        """ returns string that used as config name for criterion """
        raise NotImplementedError("Abstract methods requires overriding")


class GeneratorPlugin(object):
    DEFAULT_INFO = {
        'address': '',
        'port': 80,
        'instances': 1,
        'ammo_file': '',
        'rps_schedule': [],
        'duration': 0,
        'loop_count': 0
    }

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
        # type: () -> Info
        return self.Info(**self.DEFAULT_INFO)
