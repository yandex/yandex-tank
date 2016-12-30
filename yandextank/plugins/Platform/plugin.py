''' Module that collects remote system information '''

import getpass
import logging

from ...common.interfaces import AbstractPlugin

from ..Monitoring.collector import SecuredShell
from ..Phantom import Plugin as PhantomPlugin

logger = logging.getLogger(__name__)


class Plugin(AbstractPlugin):
    '''Plugin that collects remote system information'''
    SECTION = "platform"

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.hosts = []
        self.port = None
        self.logfile = None
        self.default_target = None

        def _echo_wrapper(cmd):
            return 'echo "====Executing: {cmd}"; {cmd}'.format(cmd=cmd)

        cmds = {
            "dpkg": "dpkg -l",
            "uname": "uname -a",
            "ulimit": "ulimit -a",
            "os_identifier": "cat /etc/issue.net",
            "uptime": "uptime",
            "cpuinfo": "cat /proc/cpuinfo",
            "meminfo": "cat /proc/meminfo",
            "free": "free -m",
            "mounts": "cat /proc/mounts",
            "df": "df -h",
            "ifconfig": "ifconfig -a",
            "sysctl": "cat /etc/sysctl.conf",
            "lsmod": "lsmod"
        }
        self.cmd = "%s" % ";\n".join(
            [_echo_wrapper(cmd) for key, cmd in cmds.iteritems()])

    def get_available_options(self):
        return ["hosts", "port", "username", "timeout"]

    def configure(self):
        try:
            hosts = self.get_option("hosts", "").strip()
            if hosts:
                self.hosts = hosts.split(" ")
            self.port = int(self.get_option("port", 22))
            self.username = self.get_option("username", getpass.getuser())
            self.timeout = int(self.get_option("timeout", 3))
        except:
            logger.error(
                'Exception trying to configure Platform plugin', exc_info=True)

        self.logfile = self.core.mkstemp(".log", "platform_")
        self.core.add_artifact_file(self.logfile)

    def prepare_test(self):
        try:
            phantom = self.core.get_plugin_of_type(PhantomPlugin)
            info = phantom.get_info()
            if info:
                if info.address and info.address not in self.hosts:
                    logger.debug(
                        "Adding platform check of default_target %s",
                        info.address)
                    self.hosts.append(info.address)
        except KeyError as ex:
            logger.debug("Phantom plugin not found: %s", ex)
        for host in self.hosts:
            self.ssh = SecuredShell(
                host, self.port, self.username, self.timeout)
            try:
                out, errors, err_code = self.ssh.execute(self.cmd)
            except Exception:
                logger.warning(
                    "Failed to check remote system information at %s:%s", host,
                    self.port)
                logger.debug(
                    "Failed to check remote system information at %s:%s",
                    host,
                    self.port,
                    exc_info=True)
            else:
                # logger.info('Remote system `%s` information: %s', host, out)
                with open(self.logfile, 'w') as f:
                    f.write(out)
                if errors:
                    logging.debug("[%s] error: '%s'", host, errors)

    def is_test_finished(self):
        return -1
