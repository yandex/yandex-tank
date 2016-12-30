""" Utility classes for phantom module """
# TODO: use separate answ log per benchmark
import copy
import logging
import multiprocessing
import string

from pkg_resources import resource_string
from yandextank.common.util import AddressWizard

from ...stepper import StepperWrapper
from ...stepper.util import parse_duration

logger = logging.getLogger(__name__)


class PhantomConfig:
    """ config file generator """
    OPTION_PHOUT = "phout_file"
    SECTION = 'phantom'

    def __init__(self, core):
        self.core = core
        self.streams = []

        # common
        self.timeout = 11000
        self.answ_log = None
        self.answ_log_level = None
        self.phout_file = None
        self.stat_log = None
        self.phantom_log = None
        self.phantom_start_time = None
        self.phantom_modules_path = None
        self.threads = None
        self.additional_libs = None
        self.enum_ammo = False

    def get_option(self, opt_name, default=None):
        """ get option wrapper """
        return self.core.get_option(self.SECTION, opt_name, default)

    @staticmethod
    def get_available_options():
        opts = [
            "threads",
            "phantom_modules_path",
            "additional_libs",
            "writelog",
            "enum_ammo",
            "timeout",
        ]
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
        self.timeout = parse_duration(self.get_option("timeout", "11s"))
        if self.timeout > 120000:
            logger.warning(
                "You've set timeout over 2 minutes."
                " Are you a functional tester?")
        self.answ_log = self.core.mkstemp(".log", "answ_")
        self.core.add_artifact_file(self.answ_log)
        self.phout_file = self.core.get_option(
            self.SECTION, self.OPTION_PHOUT, '')
        if not self.phout_file:
            self.phout_file = self.core.mkstemp(".log", "phout_")
            self.core.set_option(
                self.SECTION, self.OPTION_PHOUT, self.phout_file)
        self.core.add_artifact_file(self.phout_file)
        self.stat_log = self.core.mkstemp(".log", "phantom_stat_")
        self.core.add_artifact_file(self.stat_log)
        self.phantom_log = self.core.mkstemp(".log", "phantom_")
        self.core.add_artifact_file(self.phantom_log)

        main_stream = StreamConfig(
            self.core,
            len(self.streams), self.phout_file, self.answ_log,
            self.answ_log_level, self.timeout, self.SECTION)
        self.streams.append(main_stream)

        for section in self.core.config.find_sections(self.SECTION + '-'):
            self.streams.append(
                StreamConfig(
                    self.core,
                    len(self.streams), self.phout_file, self.answ_log,
                    self.answ_log_level, self.timeout, section))

        for stream in self.streams:
            stream.read_config()

        if any(stream.ssl for stream in self.streams):
            self.additional_libs += ' ssl io_benchmark_method_stream_transport_ssl'

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
        logger.debug("Generating phantom config: %s", filename)
        template_str = resource_string(__name__, "config/phantom.conf.tpl")
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
            logger.debug("Steps: %s", stream.stepper_wrapper.steps)
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

    def __init__(
            self, core, sequence, phout, answ, answ_level, timeout, section):
        self.core = core
        self.address_wizard = AddressWizard()

        self.sequence_no = sequence
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
        self.client_cipher_suites = None
        self.client_certificate = None
        self.client_key = None

    def get_option(self, option_ammofile, default=None):
        """ get option wrapper """
        return self.core.get_option(self.section, option_ammofile, default)

    @staticmethod
    def get_available_options():
        opts = [
            "ssl", "tank_type", 'gatling_ip', "method_prefix",
            "source_log_prefix"
        ]
        opts += [
            "phantom_http_line", "phantom_http_field_num", "phantom_http_field",
            "phantom_http_entity"
        ]
        opts += ['address', "port", StreamConfig.OPTION_INSTANCES_LIMIT]
        opts += StepperWrapper.get_available_options()
        opts += ["connection_test"]
        return opts

    def read_config(self):
        """ reads config """
        # multi-options
        self.ssl = int(self.get_option("ssl", '0'))
        self.tank_type = self.get_option("tank_type", 'http')
        # TODO: refactor. Maybe we should decide how to interact with
        # StepperWrapper here.
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
        do_test_connect = int(self.get_option("connection_test", "1")) > 0
        explicit_port = self.get_option('port', '')
        self.ipv6, self.resolved_ip, self.port, self.address = self.address_wizard.resolve(
            self.address, do_test_connect, explicit_port)

        logger.info(
            "Resolved %s into %s:%s", self.address, self.resolved_ip, self.port)

        self.client_cipher_suites = self.get_option("client_cipher_suites", "")
        self.client_certificate = self.get_option("client_certificate", "")
        self.client_key = self.get_option("client_key", "")
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
        if self.ssl:
            _auth_section = ''
            _ciphers = ''
            ssl_template = "transport_t ssl_transport = transport_ssl_t {\n" \
                           "                timeout = 1s\n" \
                           "                %s\n" \
                           "                %s}\n" \
                           "                transport = ssl_transport"

            if self.client_certificate or self.client_key:
                _auth_section = 'auth_t def_auth = auth_t { key = "%s" cert = "%s"} auth = def_auth' \
                                % (self.client_key, self.client_certificate)
            if self.client_cipher_suites:
                _ciphers = 'ciphers = "%s"' % self.client_cipher_suites
            kwargs['ssl_transport'] = ssl_template % (_auth_section, _ciphers)
        else:
            kwargs['ssl_transport'] = ""
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
        template_str = template_str = resource_string(
            __name__, "config/" + fname)
        tpl = string.Template(template_str)
        config = tpl.substitute(kwargs)

        return config


# ========================================================================
