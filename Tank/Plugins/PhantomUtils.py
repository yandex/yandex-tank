""" Utility classes for phantom module """
from ipaddr import AddressValueError
import copy
import ipaddr
import logging
import multiprocessing
import os
import socket
import string
import traceback

from Tank.stepper import StepperWrapper




# TODO: use separate answ log per benchmark
class PhantomConfig:
    """ config file generator """
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
        """ get option wrapper """
        return self.core.get_option(self.SECTION, opt_name, default)

    @staticmethod
    def get_available_options():
        opts = ["threads", "phantom_modules_path",
                "additional_libs", "writelog", ]
        opts += StreamConfig.get_available_options()
        return opts

    def read_config(self):
        """        Read phantom tool specific options        """
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
        self.phout_file = self.core.get_option(self.SECTION, self.OPTION_PHOUT, '')
        if not self.phout_file:
            self.phout_file = self.core.mkstemp(".log", "phout_")
            self.core.set_option(self.SECTION, self.OPTION_PHOUT, self.phout_file)
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
                StreamConfig(self.core, len(self.streams), self.phout_file, self.answ_log, self.answ_log_level,
                             self.timeout, section))

        for stream in self.streams:
            stream.read_config()

    def compose_config(self):
        """        Generate phantom tool run config        """
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
        tpl_file = open(os.path.dirname(__file__) + "/phantom/phantom.conf.tpl", 'r')
        template_str = tpl_file.read()
        tpl_file.close()
        tpl = string.Template(template_str)
        config = tpl.substitute(kwargs)

        handle = open(filename, 'w')
        handle.write(config)
        handle.close()
        return filename

    def set_timeout(self, timeout):
        """ pass timeout to all streams """
        for stream in self.streams:
            stream.timeout = timeout

    def get_info(self):
        """ get merged info about phantom conf """
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
                result.rps_schedule = []
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
    """ each test stream's config """

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
        """ get option wrapper """
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
        """ reads config """
        # multi-options
        self.ssl = int(self.get_option("ssl", '0'))
        self.tank_type = self.get_option("tank_type", 'http')
        # TODO: refactor. Maybe we should decide how to interact with StepperWrapper here.
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

        self.address = self.get_option('address', '127.0.0.1')
        self.port = self.get_option('port', '80')

        #address check section
        self.ip_resolved_check = False
        if not self.ip_resolved_check:
            self.__address_ipv4_check()
        if not self.ip_resolved_check:
            self.__address_ipv6_check()
        if not self.ip_resolved_check:
            self.__resolve_address()
        if not self.ip_resolved_check:
            raise RuntimeError("Address resolve/parse section failed.")
        self.stepper_wrapper.read_config()

    def compose_config(self):
        """ compose benchmark block """
        # step file
        self.stepper_wrapper.prepare_stepper()
        self.stpd = self.stepper_wrapper.stpd
        if self.stepper_wrapper.instances:
            self.instances = self.stepper_wrapper.instances

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
        tplf = open(os.path.dirname(__file__) + '/phantom/' + fname, 'r')
        template_str = tplf.read()
        tplf.close()
        tpl = string.Template(template_str)
        config = tpl.substitute(kwargs)

        return config

    def __address_ipv4_check(self):
        """ Analyse target address, IPv4 """
        self.ip_resolved_check = False
        if not self.address:
            raise RuntimeError("Target address not specified")
        #IPv4 check
        try:
            address_final = ipaddr.IPv4Address(self.address)
        except AddressValueError:
            self.log.debug("%s is not IPv4 address", self.address)
        else:
            self.ipv6 = False
            self.ip_resolved_check = True
            self.resolved_ip = address_final
            self.log.debug("%s is IPv4 address", self.address)
        #IPv4:port check
        try:
            address_port = self.address.split(":")
            address_final = ipaddr.IPv4Address(address_port[0])
        except AddressValueError, exc:
            self.log.debug("%s is not IPv4 address:port %s", self.address, traceback.format_exc(exc))
        else:
            self.ipv6 = False
            self.ip_resolved_check = True
            self.resolved_ip = address_final
            self.address = address_port[0]
            if len(address_port) > 1:
                self.port = address_port[1]
                self.log.warning(
                    "Address and port should be specified separately via 'address' and 'port' options. "
                    "Old behavior when \":\" was used as an address/port separator "
                    "is deprecated and better be avoided")
            self.log.debug(
                "%s is IPv4 address and %s is port", address_final, self.port)

    def __address_ipv6_check(self):
        """ Analyse target address, IPv6 """
        self.ip_resolved_check = False
        if not self.address:
            raise RuntimeError("Target address not specified")
        try:
            address_final = ipaddr.IPv6Address(self.address)
        except AddressValueError:
            self.log.debug(
                "%s is not IPv6 address", self.address)
        else:
            self.ipv6 = True
            self.ip_resolved_check = True
            self.resolved_ip = address_final
            self.log.debug(
                "%s is IPv6 address", address_final)

    def __resolve_address(self):
        """ Resolve hostname to IPv4/IPv6 and analyse what has been resolved """
        self.ip_resolved_check = False
        if not self.address:
            raise RuntimeError("Target address not specified")
        #address:port split
        address_port = self.address.split(":")
        if len(address_port) > 1:
            self.port = address_port[1]
            address_port = address_port[0]
            self.log.warning(
                "Address and port should be specified separately via 'address' and 'port' options. "
                "Old behavior when \":\" was used as an address/port separator "
                "is deprecated and better be avoided")
        else:
            address_port = self.address
        test_sock = None
        try:
            lookup = socket.getaddrinfo(address_port, self.port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except Exception, msg:
            logging.debug("Problems resolving target name: %s", traceback.format_exc(msg))
            raise RuntimeError("Unable to resolve hostname for %s", address_port)
        #resolve and establish a connection to resolved ip
        for res in lookup:
            af, socktype, proto, canonname, sa = res
            try:
                test_sock = socket.socket(af, socktype, proto)
            except Exception as msg:
                self.log.debug("Failed to create socket, Error code: %s", msg[0])
                test_sock = None
                continue
            try:
                test_sock.settimeout(5)
                test_sock.connect(sa)
            except socket.error as msg:
                test_sock.close()
                test_sock = None
                continue
            else:
                address_final = sa[0]
                test_sock.close()
                try:
                    ipaddr.IPv4Address(address_final)
                except AddressValueError:
                    self.log.debug("Resolved address %s is not IPv4", address_final)
                else:
                    self.ipv6 = False
                    self.ip_resolved_check = True
                    self.resolved_ip = address_final
                    self.address = address_port
                    self.log.info(
                        "Successfully established connection to resolved IPv4 %s, port %s", address_final, self.port)
                    break
                try:
                    ipaddr.IPv6Address(address_final)
                except AddressValueError:
                    self.log.debug(
                        "Resolved address %s is not IPv6", address_final)
                else:
                    self.ipv6 = True
                    self.ip_resolved_check = True
                    self.resolved_ip = address_final
                    self.address = address_port
                    self.log.info(
                        "Successfully established connection to resolved IPv6 %s, port %s", address_final, self.port)
                    break

# ========================================================================
