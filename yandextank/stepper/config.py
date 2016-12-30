import logging

from ..common.resource import manager as resource

from . import info
from . import instance_plan as ip
from . import load_plan as lp
from . import missile
from .mark import get_marker
from .module_exceptions import StepperConfigurationError, AmmoFileError


class ComponentFactory():
    def __init__(
            self,
            rps_schedule=None,
            http_ver='1.1',
            ammo_file=None,
            instances_schedule=None,
            instances=1000,
            loop_limit=-1,
            ammo_limit=-1,
            uris=None,
            headers=None,
            autocases=None,
            enum_ammo=False,
            ammo_type='phantom',
            chosen_cases=[], ):
        self.log = logging.getLogger(__name__)
        self.ammo_file = ammo_file
        self.ammo_type = ammo_type
        self.rps_schedule = rps_schedule
        self.http_ver = http_ver
        self.instances_schedule = instances_schedule
        loop_limit = int(loop_limit)
        if loop_limit == -1:  # -1 means infinite
            loop_limit = None
        ammo_limit = int(ammo_limit)
        if ammo_limit == -1:  # -1 means infinite
            ammo_limit = None
        if loop_limit is None and ammo_limit is None and not rps_schedule:
            # we should have only one loop if we have instance_schedule
            loop_limit = 1
        info.status.loop_limit = loop_limit
        info.status.ammo_limit = ammo_limit
        info.status.publish("instances", instances)
        self.uris = uris
        if self.uris and loop_limit:
            info.status.ammo_limit = len(self.uris) * loop_limit
        self.headers = headers
        self.marker = get_marker(autocases, enum_ammo)
        self.chosen_cases = chosen_cases

    def get_load_plan(self):
        """
        return load plan (timestamps generator)
        """
        if self.rps_schedule and self.instances_schedule:
            raise StepperConfigurationError(
                'Both rps and instances schedules specified. You must specify only one of them'
            )
        elif self.rps_schedule:
            info.status.publish('loadscheme', self.rps_schedule)
            return lp.create(self.rps_schedule)
        elif self.instances_schedule:
            info.status.publish('loadscheme', self.instances_schedule)
            return ip.create(self.instances_schedule)
        else:
            self.instances_schedule = []
            info.status.publish('loadscheme', self.instances_schedule)
            return ip.create(self.instances_schedule)

    def get_ammo_generator(self):
        """
        return ammo generator
        """
        af_readers = {
            'phantom': missile.AmmoFileReader,
            'slowlog': missile.SlowLogReader,
            'line': missile.LineReader,
            'uri': missile.UriReader,
            'uripost': missile.UriPostReader,
            'access': missile.AccessLogReader,
            'caseline': missile.CaseLineReader,
        }
        if self.uris and self.ammo_file:
            raise StepperConfigurationError(
                'Both uris and ammo file specified. You must specify only one of them'
            )
        elif self.uris:
            ammo_gen = missile.UriStyleGenerator(
                self.uris, self.headers, http_ver=self.http_ver)
        elif self.ammo_file:
            if self.ammo_type in af_readers:
                if self.ammo_type == 'phantom':
                    opener = resource.get_opener(self.ammo_file)
                    with opener() as ammo:
                        try:
                            if not ammo.next()[0].isdigit():
                                self.ammo_type = 'uri'
                                self.log.info(
                                    "Setting ammo_type 'uri' because ammo is not started with digit and you did not specify ammo format"
                                )
                            else:
                                self.log.info(
                                    "Default ammo type ('phantom') used, use 'phantom.ammo_type' option to override it"
                                )
                        except StopIteration:
                            self.log.exception(
                                "Couldn't read first line of ammo file")
                            raise AmmoFileError(
                                "Couldn't read first line of ammo file")
            else:
                raise NotImplementedError(
                    'No such ammo type implemented: "%s"' % self.ammo_type)
            ammo_gen = af_readers[self.ammo_type](
                self.ammo_file, headers=self.headers, http_ver=self.http_ver)
        else:
            raise StepperConfigurationError(
                'Ammo not found. Specify uris or ammo file')
        self.log.info("Using %s ammo reader" % type(ammo_gen).__name__)
        return ammo_gen

    def get_marker(self):
        return self.marker

    def get_filter(self):
        if len(self.chosen_cases):

            def is_chosen_case(ammo_tuple):
                return ammo_tuple[1] in self.chosen_cases

            return is_chosen_case
        else:
            return lambda ammo_tuple: True
