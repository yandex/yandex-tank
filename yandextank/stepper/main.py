'''
Module contains top-level generators.
'''
import hashlib
import json
import logging
import os

from builtins import zip

from netort.resource import manager as resource

from . import format as fmt
from . import info
from .config import ComponentFactory


class AmmoFactory(object):
    '''
    A generator that produces ammo.
    '''

    def __init__(self, factory):
        '''
        Factory parameter is a configured ComponentFactory that
        is able to produce load plan and ammo generator.
        '''
        self.factory = factory
        self.load_plan = factory.get_load_plan()
        self.ammo_generator = factory.get_ammo_generator()
        self.filter = factory.get_filter()
        self.marker = factory.get_marker()

    def __iter__(self):
        '''
        Returns a generator of (timestamp, marker, missile) tuples
        where missile is in a string representation. Load Plan (timestamps
        generator) and ammo generator are taken from the previously
        configured ComponentFactory, passed as a parameter to the
        __init__ method of this class.
        '''
        ammo_stream = (
            ammo
            for ammo in ((missile, marker or self.marker(missile))
                         for missile, marker in self.ammo_generator)
            if self.filter(ammo))

        return ((timestamp, marker or self.marker(missile), missile)
                for timestamp, (missile, marker
                                ) in zip(self.load_plan, ammo_stream))


class Stepper(object):
    def __init__(self, core, **kwargs):
        info.status = info.StepperStatus()
        info.status.core = core
        self.af = AmmoFactory(ComponentFactory(**kwargs))
        self.ammo = fmt.Stpd(self.af)

    def write(self, f):
        for missile in self.ammo:
            f.write(missile)
            try:
                info.status.inc_ammo_count()
            except StopIteration:
                break


class LoadProfile(object):

    def __init__(self, load_type, schedule):
        self.load_type = load_type
        self.schedule = self.__make_steps(schedule)

    def is_rps(self):
        return self.load_type == 'rps'

    def is_instances(self):
        return self.load_type == 'instances'

    @staticmethod
    def __make_steps(schedule):
        steps = []
        for step in " ".join(schedule.split("\n")).split(')'):
            if step.strip():
                steps.append(step.strip() + ')')
        return steps


class StepperWrapper(object):
    # TODO: review and rewrite this class
    '''
    Wrapper for cached stepper functionality
    '''
    OPTION_LOAD = 'load_profile'
    OPTION_LOAD_TYPE = 'load_type'
    OPTION_SCHEDULE = 'schedule'
    OPTION_STEPS = 'steps'
    OPTION_TEST_DURATION = 'test_duration'
    OPTION_AMMO_COUNT = 'ammo_count'
    OPTION_LOOP = 'loop'
    OPTION_LOOP_COUNT = 'loop_count'
    OPTION_AMMOFILE = "ammofile"
    OPTION_LOADSCHEME = 'loadscheme'
    OPTION_INSTANCES_LIMIT = 'instances'

    def __init__(self, core, cfg):
        self.log = logging.getLogger(__name__)
        self.core = core
        self.cfg = cfg

        self.cache_dir = '.'

        # per-shoot params
        self.instances = 1000
        self.http_ver = '1.0'
        self.ammo_file = None
        self.loop_limit = -1
        self.ammo_limit = -1
        self.uris = []
        self.headers = []
        self.autocases = 0
        self.enum_ammo = False
        self.force_stepping = None
        self.chosen_cases = []

        # out params
        self.stpd = None
        self.steps = []
        self.ammo_count = 1
        self.duration = 0
        self.loop_count = 0
        self.loadscheme = ""
        self.file_cache = 8192

    def get_option(self, option, param2=None):
        ''' get_option wrapper'''
        result = self.cfg[option]
        self.log.debug(
            "Option %s = %s", option, result)
        return result

    @staticmethod
    def get_available_options():
        opts = [
            StepperWrapper.OPTION_AMMOFILE, StepperWrapper.OPTION_LOOP,
            StepperWrapper.OPTION_SCHEDULE, StepperWrapper.OPTION_INSTANCES_LIMIT
        ]
        opts += [
            "instances_schedule", "uris", "headers", "header_http", "autocases",
            "enum_ammo", "ammo_type", "ammo_limit"
        ]
        opts += [
            "use_caching", "cache_dir", "force_stepping", "file_cache",
            "chosen_cases"
        ]
        return opts

    def read_config(self):
        ''' stepper part of reading options '''
        self.log.info("Configuring StepperWrapper...")
        self.ammo_file = self.get_option(self.OPTION_AMMOFILE)
        self.ammo_type = self.get_option('ammo_type')
        if self.ammo_file:
            self.ammo_file = os.path.expanduser(self.ammo_file)
        self.loop_limit = self.get_option(self.OPTION_LOOP)
        self.ammo_limit = self.get_option("ammo_limit")

        self.load_profile = LoadProfile(**self.get_option('load_profile'))

        self.instances = int(
            self.get_option(self.OPTION_INSTANCES_LIMIT, '1000'))
        self.uris = self.get_option("uris", [])
        while '' in self.uris:
            self.uris.remove('')
        self.headers = self.get_option("headers")
        self.http_ver = self.get_option("header_http")
        self.autocases = self.get_option("autocases")
        self.enum_ammo = self.get_option("enum_ammo")
        self.use_caching = self.get_option("use_caching")

        self.file_cache = self.get_option('file_cache')
        cache_dir = self.get_option("cache_dir") or self.core.artifacts_base_dir
        self.cache_dir = os.path.expanduser(cache_dir)
        self.force_stepping = self.get_option("force_stepping")
        if self.get_option(self.OPTION_LOAD)[self.OPTION_LOAD_TYPE] == 'stpd_file':
            self.stpd = self.get_option(self.OPTION_LOAD)[self.OPTION_SCHEDULE]

        self.chosen_cases = self.get_option("chosen_cases").encode('utf8').split()
        if self.chosen_cases:
            self.log.info("chosen_cases LIMITS: %s", self.chosen_cases)

    def prepare_stepper(self):
        ''' Generate test data if necessary '''

        def publish_info(stepper_info):
            info.status.publish('loadscheme', stepper_info.loadscheme)
            info.status.publish('loop_count', stepper_info.loop_count)
            info.status.publish('steps', stepper_info.steps)
            info.status.publish('duration', stepper_info.duration)
            info.status.ammo_count = stepper_info.ammo_count
            info.status.publish('instances', stepper_info.instances)
            self.core.publish('stepper', 'loadscheme', stepper_info.loadscheme)
            self.core.publish('stepper', 'loop_count', stepper_info.loop_count)
            self.core.publish('stepper', 'steps', stepper_info.steps)
            self.core.publish('stepper', 'duration', stepper_info.duration)
            self.core.publish('stepper', 'ammo_count', stepper_info.ammo_count)
            self.core.publish('stepper', 'instances', stepper_info.instances)
            return stepper_info

        if not self.stpd:
            self.stpd = self.__get_stpd_filename()
            if self.use_caching and not self.force_stepping and os.path.exists(
                    self.stpd) and os.path.exists(self.__si_filename()):
                self.log.info("Using cached stpd-file: %s", self.stpd)
                stepper_info = self.__read_cached_options()
                if self.instances and self.load_profile.is_rps():
                    self.log.info(
                        "rps_schedule is set. Overriding cached instances param from config: %s",
                        self.instances)
                    stepper_info = stepper_info._replace(
                        instances=self.instances)
                publish_info(stepper_info)
            else:
                if (
                        self.force_stepping and os.path.exists(self.__si_filename())):
                    os.remove(self.__si_filename())
                self.__make_stpd_file()
                stepper_info = info.status.get_info()
                self.__write_cached_options(stepper_info)
        else:
            self.log.info("Using specified stpd-file: %s", self.stpd)
            stepper_info = publish_info(self.__read_cached_options())
        self.ammo_count = stepper_info.ammo_count
        self.duration = stepper_info.duration
        self.loop_count = stepper_info.loop_count
        self.loadscheme = stepper_info.loadscheme
        self.steps = stepper_info.steps
        if stepper_info.instances:
            self.instances = stepper_info.instances

    def __si_filename(self):
        '''Return name for stepper_info json file'''
        return "%s_si.json" % self.stpd

    def __get_stpd_filename(self):
        ''' Choose the name for stepped data file '''
        if self.use_caching:
            sep = "|"
            hasher = hashlib.md5()
            hashed_str = "cache version 6" + sep + \
                ';'.join(self.load_profile.schedule) + sep + str(self.loop_limit)
            hashed_str += sep + str(self.ammo_limit) + sep + ';'.join(
                self.load_profile.schedule) + sep + str(self.autocases)
            hashed_str += sep + ";".join(self.uris) + sep + ";".join(
                self.headers) + sep + self.http_ver + sep + b';'.join(
                    self.chosen_cases).decode('utf8')
            hashed_str += sep + str(self.enum_ammo) + sep + str(self.ammo_type)
            if self.load_profile.is_instances():
                hashed_str += sep + str(self.instances)
            if self.ammo_file:
                opener = resource.get_opener(self.ammo_file)
                hashed_str += sep + opener.hash
            else:
                if not self.uris:
                    raise RuntimeError("Neither ammofile nor uris specified")
                hashed_str += sep + \
                    ';'.join(self.uris) + sep + ';'.join(self.headers)
            self.log.debug("stpd-hash source: %s", hashed_str)
            hasher.update(hashed_str.encode('utf8'))
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
            stpd = self.cache_dir + '/' + \
                os.path.basename(self.ammo_file) + \
                "_" + hasher.hexdigest() + ".stpd"
        else:
            stpd = os.path.realpath("ammo.stpd")
        self.log.debug("Generated cache file name: %s", stpd)
        return stpd

    def __read_cached_options(self):
        '''
        Read stepper info from json
        '''
        self.log.debug("Reading cached stepper info: %s", self.__si_filename())
        with open(self.__si_filename(), 'r') as si_file:
            si = info.StepperInfo(**json.load(si_file))
        return si

    def __write_cached_options(self, si):
        '''
        Write stepper info to json
        '''
        self.log.debug("Saving stepper info: %s", self.__si_filename())
        with open(self.__si_filename(), 'w') as si_file:
            json.dump(si._asdict(), si_file, indent=4)

    def __make_stpd_file(self):
        ''' stpd generation using Stepper class '''
        self.log.info("Making stpd-file: %s", self.stpd)
        stepper = Stepper(
            self.core,
            rps_schedule=self.load_profile.schedule if self.load_profile.is_rps() else None,
            http_ver=self.http_ver,
            ammo_file=self.ammo_file,
            instances_schedule=self.load_profile.schedule if self.load_profile.is_instances() else None,
            instances=self.instances,
            loop_limit=self.loop_limit,
            ammo_limit=self.ammo_limit,
            uris=self.uris,
            headers=[header.strip('[]') for header in self.headers],
            autocases=self.autocases,
            enum_ammo=self.enum_ammo,
            ammo_type=self.ammo_type,
            chosen_cases=self.chosen_cases,
            use_cache=self.use_caching)
        with open(self.stpd, 'wb', self.file_cache) as os:
            stepper.write(os)
