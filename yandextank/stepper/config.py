import logging
from typing import Optional
from yandextank.contrib.netort.netort.resource import ResourceManager, manager

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
            autocases=0,
            enum_ammo=False,
            ammo_type='phantom',
            chosen_cases=None,
            use_cache=True,
            resource_manager: Optional[ResourceManager] = None,
    ):
        self.log = logging.getLogger(__name__)
        self.ammo_file = ammo_file
        self._ammo_type_unchecked = ammo_type
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
        self.headers = headers if headers is not None else []
        self.marker = get_marker(autocases, enum_ammo)
        self.chosen_cases = chosen_cases or []
        self.use_cache = use_cache
        self.resource_manager = resource_manager or manager

    @property
    def ammo_type(self):
        if self._ammo_type_unchecked != 'phantom':
            return self._ammo_type_unchecked

        opener = self.resource_manager.get_opener(self.ammo_file)
        with opener(self.use_cache) as ammo:
            try:
                ammo_str = next(ammo).decode('utf-8')
            except StopIteration:
                self.log.exception(
                    "Couldn't read first line of ammo file")
                raise AmmoFileError(
                    "Couldn't read first line of ammo file")

            if not ammo_str[0].isdigit():
                self.log.info(
                    "Setting ammo_type 'uri' because ammo is not started with digit and you did not specify ammo format"
                )
                return 'uri'
            self.log.info(
                "Default ammo type ('phantom') used, use 'phantom.ammo_type' option to override it"
            )
            return self._ammo_type_unchecked

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

    def _check_exactly_one_source_specified(self):
        sources = {
            'uris': self.uris,
            'ammo_file': self.ammo_file
        }
        active_sources = {k: v for k, v in sources.items() if v}
        if len(active_sources) != 1:
            self.log.error('active sources: %s', active_sources)
            raise StepperConfigurationError(
                f'Exactly one of sources {list(sources.keys())} should be specified, '
                f'but found {list(active_sources.keys())} in config.')

    def _get_ammo_generator(self):
        self._check_exactly_one_source_specified()
        if self.uris:
            return missile.UriStyleGenerator(self.uris, self.headers, http_ver=self.http_ver)

        if self.ammo_type not in missile.FILE_READERS:
            raise NotImplementedError(
                'No such ammo type implemented: "%s"' % self.ammo_type)

        return missile.FILE_READERS[self.ammo_type](
            self.ammo_file, headers=self.headers, http_ver=self.http_ver, use_cache=self.use_cache, resource_manager=self.resource_manager)

    def get_ammo_generator(self):
        ammo_gen = self._get_ammo_generator()
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
