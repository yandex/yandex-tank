''' Utility classes for phantom module '''
import Tank.stepper as stp
from ipaddr import AddressValueError
import copy
import hashlib
import ipaddr
import logging
import multiprocessing
import os
import socket
import string
import json


# TODO: use separate answ log per benchmark
class PhantomConfig:

    ''' config file generator '''
    OPTION_PHOUT = "phout_file"
    SECTION = 'phantom'

    def __init__(self, core):
        self.core = core
        self.log = logging.getLogger(__name__)
        self.streams = []

        # common
        self.timeout = -1
        self.answ_log = None
        self.answ_log_level = None
        self.phout_file = None
        self.stat_log = None
        self.phantom_log = None
        self.phantom_start_time = None
        self.phantom_modules_path = None
        self.threads = None
        self.additional_libs = None

    def get_option(self, opt_name, default=None):
        ''' get option wrapper '''
        return self.core.get_option(self.SECTION, opt_name, default)

    @staticmethod
    def get_available_options():
        opts = ["threads", "phantom_modules_path",
                "additional_libs", "writelog", ]
        opts += StreamConfig.get_available_options()
        return opts

    def read_config(self):
        '''        Read phantom tool specific options        '''
        self.threads = self.get_option(
            "threads", str(int(multiprocessing.cpu_count() / 2) + 1))
        self.phantom_modules_path = self.get_option(
            "phantom_modules_path", "/usr/lib/phantom")
        self.additional_libs = self.get_option("additional_libs", "")
        self.answ_log_level = self.get_option("writelog", "none")
        if self.answ_log_level == '0':
            self.answ_log_level = 'none'
        elif self.answ_log_level == '1':
            self.answ_log_level = 'all'

        self.answ_log = self.core.mkstemp(".log", "answ_")
        self.core.add_artifact_file(self.answ_log)
        self.phout_file = self.core.mkstemp(".log", "phout_")
        self.core.add_artifact_file(self.phout_file)
        self.stat_log = self.core.mkstemp(".log", "phantom_stat_")
        self.core.add_artifact_file(self.stat_log)
        self.phantom_log = self.core.mkstemp(".log", "phantom_")
        self.core.add_artifact_file(self.phantom_log)

        main_stream = StreamConfig(
            self.core, len(self.streams), self.phout_file,
            self.answ_log, self.answ_log_level, self.timeout, self.SECTION)
        self.streams.append(main_stream)

        for section in self.core.config.find_sections(self.SECTION + '-'):
            self.streams.append(
                StreamConfig(self.core, len(self.streams), self.phout_file, self.answ_log, self.answ_log_level, self.timeout, section))

        for stream in self.streams:
            stream.read_config()

    def compose_config(self):
        '''        Generate phantom tool run config        '''
        streams_config = ''
        stat_benchmarks = ''
        for stream in self.streams:
            streams_config += stream.compose_config()
            if stream.section != self.SECTION:
                stat_benchmarks += " " + "benchmark_io%s" % stream.sequence_no

        kwargs = {}
        kwargs['threads'] = self.threads
        kwargs['phantom_log'] = self.phantom_log
        kwargs['stat_log'] = self.stat_log
        kwargs['benchmarks_block'] = streams_config
        kwargs['stat_benchmarks'] = stat_benchmarks
        kwargs['additional_libs'] = self.additional_libs
        kwargs['phantom_modules_path'] = self.phantom_modules_path
        filename = self.core.mkstemp(".conf", "phantom_")
        self.core.add_artifact_file(filename)
        self.log.debug("Generating phantom config: %s", filename)
        tpl_file = open(os.path.dirname(__file__) + "/phantom.conf.tpl", 'r')
        template_str = tpl_file.read()
        tpl_file.close()
        tpl = string.Template(template_str)
        config = tpl.substitute(kwargs)

        handle = open(filename, 'w')
        handle.write(config)
        handle.close()
        return filename

    def set_timeout(self, timeout):
        ''' pass timeout to all streams '''
        for stream in self.streams:
            stream.timeout = timeout

    def get_info(self):
        ''' get merged info about phantom conf '''
        result = copy.copy(self.streams[0])
        result.stat_log = self.stat_log
        result.steps = []
        result.ammo_file = ''
        result.rps_schedule = None
        result.ammo_count = 0
        result.duration = 0

        result.instances = 0
        result.loadscheme = []
        result.loop_count = 0

        for stream in self.streams:
            sec_no = 0
            logging.debug("Steps: %s", stream.stepper_wrapper.steps)
            for item in stream.stepper_wrapper.steps:
                for x in range(0, item[1]):
                    if len(result.steps) > sec_no:
                        result.steps[sec_no][0] += item[0]
                    else:
                        result.steps.append([item[0], 1])
                    sec_no += 1

            if result.rps_schedule:
                result.rps_schedule = u'multiple'
            else:
                result.rps_schedule = stream.stepper_wrapper.loadscheme
            if result.loadscheme:
                result.loadscheme = ''
            else:
                # FIXME: add formatted load scheme for server:
                # <step_size,step_type,first_rps,last_rps,original_step_params>
                # as a string
                result.loadscheme = ''

            if result.loop_count:
                result.loop_count = u'0'
            else:
                result.loop_count = stream.stepper_wrapper.loop_count

            result.ammo_file += stream.stepper_wrapper.ammo_file + ' '
            result.ammo_count += stream.stepper_wrapper.ammo_count
            result.duration = max(
                result.duration, stream.stepper_wrapper.duration)
            result.instances += stream.instances

        if not result.ammo_count:
            raise ValueError("Total ammo count cannot be zero")
        return result


class StreamConfig:

    ''' each test stream's config '''

    OPTION_INSTANCES_LIMIT = 'instances'

    def __init__(self, core, sequence, phout, answ, answ_level, timeout, section):
        self.core = core
        self.sequence_no = sequence
        self.log = logging.getLogger(__name__)
        self.section = section
        self.stepper_wrapper = StepperWrapper(self.core, self.section)
        self.phout_file = phout
        self.answ_log = answ
        self.answ_log_level = answ_level
        self.timeout = timeout

        # per benchmark
        self.instances = None
        self.ipv6 = None
        self.ssl = None
        self.address = None
        self.port = None
        self.tank_type = None
        self.stpd = None
        self.gatling = None
        self.phantom_http_line = None
        self.phantom_http_field_num = None
        self.phantom_http_field = None
        self.phantom_http_entity = None
        self.resolved_ip = None
        self.method_prefix = None
        self.source_log_prefix = None
        self.method_options = None

    def get_option(self, option_ammofile, default=None):
        ''' get option wrapper '''
        return self.core.get_option(self.section, option_ammofile, default)

    @staticmethod
    def get_available_options():
        opts = ["ssl", "tank_type", 'gatling_ip',
                "method_prefix", "source_log_prefix"]
        opts += ["phantom_http_line", "phantom_http_field_num",
                 "phantom_http_field", "phantom_http_entity"]
        opts += ['address', "port", StreamConfig.OPTION_INSTANCES_LIMIT]
        opts += StepperWrapper.get_available_options()
        return opts

    def read_config(self):
        ''' reads config '''
        # multi-options
        self.ssl = int(self.get_option("ssl", '0'))
        self.tank_type = self.get_option("tank_type", 'http')
        self.instances = int(
            self.get_option(self.OPTION_INSTANCES_LIMIT, '1000'))
        self.gatling = ' '.join(self.get_option('gatling_ip', '').split("\n"))
        self.method_prefix = self.get_option("method_prefix", 'method_stream')
        self.method_options = self.get_option("method_options", '')
        self.source_log_prefix = self.get_option("source_log_prefix", '')

        self.phantom_http_line = self.get_option("phantom_http_line", "")
        self.phantom_http_field_num = self.get_option(
            "phantom_http_field_num", "")
        self.phantom_http_field = self.get_option("phantom_http_field", "")
        self.phantom_http_entity = self.get_option("phantom_http_entity", "")

        self.address = self.get_option('address', 'localhost')
        self.port = self.get_option('port', '80')
        self.__resolve_address()

        self.stepper_wrapper.read_config()

    def compose_config(self):
        ''' compose benchmark block '''
        # step file
        self.stepper_wrapper.prepare_stepper()
        self.stpd = self.stepper_wrapper.stpd

        if not self.stpd:
            raise RuntimeError("Cannot proceed with no STPD file")

        kwargs = {}
        kwargs['sequence_no'] = self.sequence_no
        kwargs[
            'ssl_transport'] = "transport_t ssl_transport = transport_ssl_t { timeout = 1s }\n transport = ssl_transport" if self.ssl else ""
        kwargs['method_stream'] = self.method_prefix + \
            "_ipv6_t" if self.ipv6 else self.method_prefix + "_ipv4_t"
        kwargs['phout'] = self.phout_file
        kwargs['answ_log'] = self.answ_log
        kwargs['answ_log_level'] = self.answ_log_level
        kwargs['comment_answ'] = "# " if self.answ_log_level == 'none' else ''
        kwargs['stpd'] = self.stpd
        kwargs['source_log_prefix'] = self.source_log_prefix
        kwargs['method_options'] = self.method_options
        if self.tank_type:
            kwargs[
                'proto'] = "proto=http_proto%s" % self.sequence_no if self.tank_type == 'http' else "proto=none_proto"
            kwargs['comment_proto'] = ""
        else:
            kwargs['proto'] = ""
            kwargs['comment_proto'] = "#"

        if self.gatling:
            kwargs['bind'] = 'bind={ ' + self.gatling + ' }'
        else:
            kwargs['bind'] = ''
        kwargs['ip'] = self.resolved_ip
        kwargs['port'] = self.port
        kwargs['timeout'] = self.timeout
        kwargs['instances'] = self.instances
        tune = ''
        if self.phantom_http_entity:
            tune += "entity = " + self.phantom_http_entity + "\n"
        if self.phantom_http_field:
            tune += "field = " + self.phantom_http_field + "\n"
        if self.phantom_http_field_num:
            tune += "field_num = " + self.phantom_http_field_num + "\n"
        if self.phantom_http_line:
            tune += "line = " + self.phantom_http_line + "\n"
        if tune:
            kwargs['reply_limits'] = 'reply_limits = {\n' + tune + "}"
        else:
            kwargs['reply_limits'] = ''

        if self.section == PhantomConfig.SECTION:
            fname = 'phantom_benchmark_main.tpl'
        else:
            fname = 'phantom_benchmark_additional.tpl'
        tplf = open(os.path.dirname(__file__) + '/' + fname, 'r')
        template_str = tplf.read()
        tplf.close()
        tpl = string.Template(template_str)
        config = tpl.substitute(kwargs)

        return config

    # FIXME: this method became a piece of shit, needs refactoring
    def __resolve_address(self):
        ''' Analyse target address setting, resolve it to IP '''
        if not self.address:
            raise RuntimeError("Target address not specified")
        try:
            ipaddr.IPv6Address(self.address)
            self.ipv6 = True
            self.resolved_ip = self.address
            try:
                self.address = socket.gethostbyaddr(self.resolved_ip)[0]
            except Exception, exc:
                self.log.debug("Failed to get hostname for ip: %s", exc)
                self.address = self.resolved_ip
        except AddressValueError:
            self.log.debug("Not ipv6 address: %s", self.address)
            self.ipv6 = False
            address_port = self.address.split(":")
            self.address = address_port[0]
            if len(address_port) > 1:
                self.port = address_port[1]
            try:
                ipaddr.IPv4Address(self.address)
                self.resolved_ip = self.address
                try:
                    self.address = socket.gethostbyaddr(self.resolved_ip)[0]
                except Exception, exc:
                    self.log.debug("Failed to get hostname for ip: %s", exc)
                    self.address = self.resolved_ip
            except AddressValueError:
                self.log.debug("Not ipv4 address: %s", self.address)
                ip_addr = socket.gethostbyname(self.address)
                reverse_name = socket.gethostbyaddr(ip_addr)[0]
                self.log.debug(
                    "Address %s ip_addr: %s, reverse-resolve: %s", self.address, ip_addr, reverse_name)
                if reverse_name.startswith(self.address):
                    self.resolved_ip = ip_addr
                else:
                    raise ValueError(
                        "Address %s reverse-resolved to %s, but must match" % (self.address, reverse_name))

# ========================================================================


class StepperWrapper:

    '''
    Wrapper for cached stepper functionality
    '''
    OPTION_STPD = 'stpd_file'
    OPTION_STEPS = 'steps'
    OPTION_TEST_DURATION = 'test_duration'
    OPTION_AMMO_COUNT = 'ammo_count'
    OPTION_LOOP = 'loop'
    OPTION_LOOP_COUNT = 'loop_count'
    OPTION_AMMOFILE = "ammofile"
    OPTION_SCHEDULE = 'rps_schedule'
    OPTION_LOADSCHEME = 'loadscheme'

    def __init__(self, core, section):
        self.log = logging.getLogger(__name__)
        self.core = core
        self.section = section

        self.cache_dir = '.'

        # per-shoot params
        self.rps_schedule = []
        self.http_ver = '1.0'
        self.ammo_file = None
        self.instances_schedule = ''
        self.loop_limit = None
        self.ammo_limit = None
        self.uris = []
        self.headers = []
        self.autocases = 0
        self.use_caching = True
        self.force_stepping = None

        # out params
        self.stpd = None
        self.steps = []
        self.ammo_count = 1
        self.duration = 0
        self.loop_count = 0
        self.loadscheme = ""
        self.file_cache = 8192

    def get_option(self, option_ammofile, param2=None):
        ''' get_option wrapper'''
        return self.core.get_option(self.section, option_ammofile, param2)

    @staticmethod
    def get_available_options():
        opts = [StepperWrapper.OPTION_AMMOFILE, StepperWrapper.OPTION_LOOP,
                StepperWrapper.OPTION_SCHEDULE, StepperWrapper.OPTION_STPD]
        opts += ["instances_schedule", "uris",
                 "headers", "header_http", "autocases", ]
        opts += ["use_caching", "cache_dir", "force_stepping", "file_cache"]
        return opts

    def read_config(self):
        ''' stepper part of reading options '''
        self.ammo_file = self.get_option(self.OPTION_AMMOFILE, '')
        if self.ammo_file:
            self.ammo_file = os.path.expanduser(self.ammo_file)
        self.loop_limit = int(self.get_option(self.OPTION_LOOP, "-1"))
        self.ammo_limit = int(self.get_option("ammo_limit", "-1"))
        # TODO: 3 stepper should implement ammo_limit

        def make_steps(schedule):
            steps = []
            for step in " ".join(schedule.split("\n")).split(')'):
                if step.strip():
                    steps.append(step.strip() + ')')
            return steps
        self.rps_schedule = make_steps(
            self.get_option(self.OPTION_SCHEDULE, ''))
        self.instances_schedule = make_steps(
            self.get_option("instances_schedule", ''))

        self.uris = self.get_option("uris", '').strip().split("\n")
        while '' in self.uris:
            self.uris.remove('')
        self.headers = self.get_option("headers", '').strip().split("\n")
        while '' in self.headers:
            self.headers.remove('')
        self.http_ver = self.get_option("header_http", self.http_ver)
        self.autocases = self.get_option("autocases", '0')
        self.use_caching = int(self.get_option("use_caching", '1'))

        self.file_cache = int(self.get_option('file_cache', '8192'))
        cache_dir = self.core.get_option(
            PhantomConfig.SECTION, "cache_dir", self.core.artifacts_base_dir)
        self.cache_dir = os.path.expanduser(cache_dir)
        self.force_stepping = int(self.get_option("force_stepping", '0'))
        self.stpd = self.get_option(self.OPTION_STPD, "")

    def prepare_stepper(self):
        ''' Generate test data if necessary '''
        if not self.stpd:
            self.stpd = self.__get_stpd_filename()
            self.core.set_option(self.section, self.OPTION_STPD, self.stpd)
            if self.use_caching and not self.force_stepping and os.path.exists(self.stpd) and os.path.exists(self.__si_filename()):
                self.log.info("Using cached stpd-file: %s", self.stpd)
                stepper_info = self.__read_cached_options()
            else:
                if self.force_stepping and os.path.exists(self.__si_filename()):
                    os.remove(self.__si_filename())
                stepper_info = self.__make_stpd_file()
                self.__write_cached_options(stepper_info)
            self.ammo_count = stepper_info.ammo_count
            self.duration = stepper_info.duration
            self.loop_count = stepper_info.loop_count
            self.loadscheme = stepper_info.loadscheme
            self.steps = stepper_info.steps

    def __si_filename(self):
        '''Return name for stepper_info json file'''
        return "%s_si.json" % self.stpd

    def __get_stpd_filename(self):
        ''' Choose the name for stepped data file '''
        if self.use_caching:
            sep = "|"
            hasher = hashlib.md5()
            hashed_str = "cache version 3" + sep + \
                ';'.join(self.instances_schedule) + sep + str(self.loop_limit)
            hashed_str += sep + str(self.ammo_limit) + sep + ';'.join(
                self.rps_schedule) + sep + str(self.autocases)
            hashed_str += sep + \
                ";".join(self.uris) + sep + ";".join(
                    self.headers) + sep + self.http_ver

            if self.ammo_file:
                if not os.path.exists(self.ammo_file):
                    raise RuntimeError(
                        "Ammo file not found: %s" % self.ammo_file)

                hashed_str += sep + os.path.realpath(self.ammo_file)
                stat = os.stat(self.ammo_file)
                cnt = 0
                for stat_option in stat:
                    if cnt == 7:  # skip access time
                        continue
                    cnt += 1
                    hashed_str += ";" + str(stat_option)
                hashed_str += ";" + str(os.path.getmtime(self.ammo_file))
            else:
                if not self.uris:
                    raise RuntimeError(
                        "Neither phantom.ammofile nor phantom.uris specified")
                hashed_str += sep + \
                    ';'.join(self.uris) + sep + ';'.join(self.headers)
            self.log.debug("stpd-hash source: %s", hashed_str)
            hasher.update(hashed_str)
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
            si = stp.StepperInfo(**json.load(si_file))
        return si

    def __write_cached_options(self, si):
        '''
        Write stepper info to json
        '''
        # TODO: format json
        self.log.debug("Saving stepper info: %s", self.__si_filename())
        with open(self.__si_filename(), 'w') as si_file:
            json.dump(si.__dict__, si_file, indent=4)

    def __make_stpd_file(self):
        ''' stpd generation using Stepper class '''
        self.log.info("Making stpd-file: %s", self.stpd)
        stepper = stp.Stepper(
            rps_schedule=self.rps_schedule,
            http_ver=self.http_ver,
            ammo_file=self.ammo_file,
            instances_schedule=self.instances_schedule,
            loop_limit=self.loop_limit,
            ammo_limit=self.ammo_limit,
            uris=self.uris,
            headers=[header.strip('[]') for header in self.headers],
            autocases=self.autocases,
        )
        with open(self.stpd, 'w', self.file_cache) as os:
            stepper.write(os)
        return stepper.info
