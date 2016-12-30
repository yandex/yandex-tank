'''
Common utilities
'''
import os
import socket
import threading as th
import traceback

import http.client
import logging
import errno
import itertools
import re
import select
import shlex
import psutil
import subprocess
import argparse
from paramiko import SSHClient, AutoAddPolicy

logger = logging.getLogger(__name__)


class Drain(th.Thread):
    """
    Drain a generator to a destination that answers to put(), in a thread
    """

    def __init__(self, source, destination):
        super(Drain, self).__init__()
        self.source = source
        self.destination = destination
        self._interrupted = th.Event()

    def run(self):
        for item in self.source:
            self.destination.put(item)
            if self._interrupted.is_set():
                break

    def close(self):
        self._interrupted.set()


class SecuredShell(object):
    def __init__(self, host, port, username, timeout):
        self.host = host
        self.port = port
        self.username = username
        self.timeout = timeout

    def connect(self):
        logger.debug(
            "Opening SSH connection to {host}:{port}".format(
                host=self.host, port=self.port))
        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy())

        try:
            client.connect(
                self.host,
                port=self.port,
                username=self.username,
                timeout=self.timeout, )
        except ValueError as e:
            logger.error(e)
            logger.warning(
                """
Patching Crypto.Cipher.AES.new and making another attempt.

See here for the details:
http://uucode.com/blog/2015/02/20/workaround-for-ctr-mode-needs-counter-parameter-not-iv/
            """)
            client.close()
            import Crypto.Cipher.AES
            orig_new = Crypto.Cipher.AES.new

            def fixed_AES_new(key, *ls):
                if Crypto.Cipher.AES.MODE_CTR == ls[0]:
                    ls = list(ls)
                    ls[1] = ''
                return orig_new(key, *ls)

            Crypto.Cipher.AES.new = fixed_AES_new
            client.connect(
                self.host,
                port=self.port,
                username=self.username,
                timeout=self.timeout, )
        return client

    def execute(self, cmd):
        logger.info("Execute on %s: %s", self.host, cmd)
        with self.connect() as client:
            _, stdout, stderr = client.exec_command(cmd)
            output = stdout.read()
            errors = stderr.read()
            err_code = stdout.channel.recv_exit_status()
        return output, errors, err_code

    def rm(self, path):
        return self.execute("rm -f %s" % path)

    def rm_r(self, path):
        return self.execute("rm -rf %s" % path)

    def mkdir(self, path):
        return self.execute("mkdir -p %s" % path)

    def send_file(self, local_path, remote_path):
        logger.info(
            "Sending [{local}] to {host}:[{remote}]".format(
                local=local_path, host=self.host, remote=remote_path))
        with self.connect() as client, client.open_sftp() as sftp:
            result = sftp.put(local_path, remote_path)
        return result

    def get_file(self, remote_path, local_path):
        logger.info(
            "Receiving from {host}:[{remote}] to [{local}]".format(
                local=local_path, host=self.host, remote=remote_path))
        with self.connect() as client, client.open_sftp() as sftp:
            result = sftp.get(remote_path, local_path)
        return result

    def async_session(self, cmd):
        return AsyncSession(self, cmd)


def check_ssh_connection():
    logging.basicConfig(
        level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger("paramiko.transport").setLevel(logging.DEBUG)

    parser = argparse.ArgumentParser(
        description='Test SSH connection for monitoring.')
    parser.add_argument(
        '-e', '--endpoint', default='example.org', help='which host to try')

    parser.add_argument(
        '-u', '--username', default=os.getlogin(), help='SSH username')

    parser.add_argument('-p', '--port', default=22, type=int, help='SSH port')
    args = parser.parse_args()
    logging.info(
        "Checking SSH to %s@%s:%d", args.username, args.endpoint, args.port)
    ssh = SecuredShell(args.endpoint, args.port, args.username, 10)
    print(ssh.execute("ls -l"))


class AsyncSession(object):
    def __init__(self, ssh, cmd):
        self.client = ssh.connect()
        self.session = self.client.get_transport().open_session()
        self.session.get_pty()
        self.session.exec_command(cmd)

    def send(self, data):
        self.session.send(data)

    def close(self):
        self.session.close()
        self.client.close()

    def finished(self):
        return self.session.exit_status_ready()

    def read_maybe(self):
        if self.session.recv_ready():
            return self.session.recv(4096)
        else:
            return None


# HTTP codes
HTTP = http.client.responses

# Extended list of HTTP status codes(WEBdav etc.)
# HTTP://en.wikipedia.org/wiki/List_of_HTTP_status_codes
WEBDAV = {
    102: 'Processing',
    103: 'Checkpoint',
    122: 'Request-URI too long',
    207: 'Multi-Status',
    226: 'IM Used',
    308: 'Resume Incomplete',
    418: 'I\'m a teapot',
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    425: 'Unordered Collection',
    426: 'Upgrade Required',
    444: 'No Response',
    449: 'Retry With',
    450: 'Blocked by Windows Parental Controls',
    499: 'Client Closed Request',
    506: 'Variant Also Negotiates',
    507: 'Insufficient Storage',
    509: 'Bandwidth Limit Exceeded',
    510: 'Not Extended',
    598: 'network read timeout error',
    599: 'network connect timeout error',
    999: 'Common Failure',
}
HTTP.update(WEBDAV)

# NET codes
NET = {
    0: "Success",
    1: "Operation not permitted",
    2: "No such file or directory",
    3: "No such process",
    4: "Interrupted system call",
    5: "Input/output error",
    6: "No such device or address",
    7: "Argument list too long",
    8: "Exec format error",
    9: "Bad file descriptor",
    10: "No child processes",
    11: "Resource temporarily unavailable",
    12: "Cannot allocate memory",
    13: "Permission denied",
    14: "Bad address",
    15: "Block device required",
    16: "Device or resource busy",
    17: "File exists",
    18: "Invalid cross-device link",
    19: "No such device",
    20: "Not a directory",
    21: "Is a directory",
    22: "Invalid argument",
    23: "Too many open files in system",
    24: "Too many open files",
    25: "Inappropriate ioctl for device",
    26: "Text file busy",
    27: "File too large",
    28: "No space left on device",
    29: "Illegal seek",
    30: "Read-only file system",
    31: "Too many links",
    32: "Broken pipe",
    33: "Numerical argument out of domain",
    34: "Numerical result out of range",
    35: "Resource deadlock avoided",
    36: "File name too long",
    37: "No locks available",
    38: "Function not implemented",
    39: "Directory not empty",
    40: "Too many levels of symbolic links",
    41: "Unknown error 41",
    42: "No message of desired type",
    43: "Identifier removed",
    44: "Channel number out of range",
    45: "Level 2 not synchronized",
    46: "Level 3 halted",
    47: "Level 3 reset",
    48: "Link number out of range",
    49: "Protocol driver not attached",
    50: "No CSI structure available",
    51: "Level 2 halted",
    52: "Invalid exchange",
    53: "Invalid request descriptor",
    54: "Exchange full",
    55: "No anode",
    56: "Invalid request code",
    57: "Invalid slot",
    58: "Unknown error 58",
    59: "Bad font file format",
    60: "Device not a stream",
    61: "No data available",
    62: "Timer expired",
    63: "Out of streams resources",
    64: "Machine is not on the network",
    65: "Package not installed",
    66: "Object is remote",
    67: "Link has been severed",
    68: "Advertise error",
    69: "Srmount error",
    70: "Communication error on send",
    71: "Protocol error",
    72: "Multihop attempted",
    73: "RFS specific error",
    74: "Bad message",
    75: "Value too large for defined data type",
    76: "Name not unique on network",
    77: "File descriptor in bad state",
    78: "Remote address changed",
    79: "Can not access a needed shared library",
    80: "Accessing a corrupted shared library",
    81: ".lib section in a.out corrupted",
    82: "Attempting to link in too many shared libraries",
    83: "Cannot exec a shared library directly",
    84: "Invalid or incomplete multibyte or wide character",
    85: "Interrupted system call should be restarted",
    86: "Streams pipe error",
    87: "Too many users",
    88: "Socket operation on non-socket",
    89: "Destination address required",
    90: "Message too long",
    91: "Protocol wrong type for socket",
    92: "Protocol not available",
    93: "Protocol not supported",
    94: "Socket type not supported",
    95: "Operation not supported",
    96: "Protocol family not supported",
    97: "Address family not supported by protocol",
    98: "Address already in use",
    99: "Cannot assign requested address",
    100: "Network is down",
    101: "Network is unreachable",
    102: "Network dropped connection on reset",
    103: "Software caused connection abort",
    104: "Connection reset by peer",
    105: "No buffer space available",
    106: "Transport endpoint is already connected",
    107: "Transport endpoint is not connected",
    108: "Cannot send after transport endpoint shutdown",
    109: "Too many references: cannot splice",
    110: "Connection timed out",
    111: "Connection refused",
    112: "Host is down",
    113: "No route to host",
    114: "Operation already in progress",
    115: "Operation now in progress",
    116: "Stale NFS file handle",
    117: "Structure needs cleaning",
    118: "Not a XENIX named type file",
    119: "No XENIX semaphores available",
    120: "Is a named type file",
    121: "Remote I/O error",
    122: "Disk quota exceeded",
    123: "No medium found",
    124: "Wrong medium type",
    125: "Operation canceled",
    126: "Required key not available",
    127: "Key has expired",
    128: "Key has been revoked",
    129: "Key was rejected by service",
    130: "Owner died",
    131: "State not recoverable",
    999: 'Common Failure',
}


def log_stdout_stderr(log, stdout, stderr, comment=""):
    """
    This function polls stdout and stderr streams and writes their contents
    to log
    """
    readable = select.select([stdout], [], [], 0)[0]
    if stderr:
        exceptional = select.select([stderr], [], [], 0)[0]
    else:
        exceptional = []

    log.debug("Selected: %s, %s", readable, exceptional)

    for handle in readable:
        line = handle.read()
        readable.remove(handle)
        if line:
            log.debug("%s stdout: %s", comment, line.strip())

    for handle in exceptional:
        line = handle.read()
        exceptional.remove(handle)
        if line:
            log.warn("%s stderr: %s", comment, line.strip())


def expand_to_milliseconds(str_time):
    """
    converts 1d2s into milliseconds
    """
    return expand_time(str_time, 'ms', 1000)


def expand_to_seconds(str_time):
    """
    converts 1d2s into seconds
    """
    return expand_time(str_time, 's', 1)


def expand_time(str_time, default_unit='s', multiplier=1):
    """
    helper for above functions
    """
    parser = re.compile('(\d+)([a-zA-Z]*)')
    parts = parser.findall(str_time)
    result = 0.0
    for value, unit in parts:
        value = int(value)
        unit = unit.lower()
        if unit == '':
            unit = default_unit

        if unit == 'ms':
            result += value * 0.001
            continue
        elif unit == 's':
            result += value
            continue
        elif unit == 'm':
            result += value * 60
            continue
        elif unit == 'h':
            result += value * 60 * 60
            continue
        elif unit == 'd':
            result += value * 60 * 60 * 24
            continue
        elif unit == 'w':
            result += value * 60 * 60 * 24 * 7
            continue
        else:
            raise ValueError(
                "String contains unsupported unit %s: %s" % (unit, str_time))
    return int(result * multiplier)


def pid_exists(pid):
    """Check whether pid exists in the current process table."""
    if pid < 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        logging.debug("No process[%s]: %s", exc.errno, exc)
        return exc.errno == errno.EPERM
    else:
        p = psutil.Process(pid)
        return p.status != psutil.STATUS_ZOMBIE


def execute(cmd, shell=False, poll_period=1.0, catch_out=False):
    """
    Wrapper for Popen
    """
    log = logging.getLogger(__name__)
    log.debug("Starting: %s", cmd)

    stdout = ""
    stderr = ""

    if not shell and isinstance(cmd, basestring):
        cmd = shlex.split(cmd)

    if catch_out:
        process = subprocess.Popen(
            cmd,
            shell=shell,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            close_fds=True)
    else:
        process = subprocess.Popen(cmd, shell=shell, close_fds=True)

    stdout, stderr = process.communicate()
    if stderr:
        log.error("There were errors:\n%s", stderr)

    if stdout:
        log.debug("Process output:\n%s", stdout)
    returncode = process.returncode
    log.debug("Process exit code: %s", returncode)
    return returncode, stdout, stderr


def splitstring(string):
    """
    >>> string = 'apple orange "banana tree" green'
    >>> splitstring(string)
    ['apple', 'orange', 'green', '"banana tree"']
    """
    patt = re.compile(r'"[\w ]+"')
    if patt.search(string):
        quoted_item = patt.search(string).group()
        newstring = patt.sub('', string)
        return newstring.split() + [quoted_item]
    else:
        return string.split()


def pairs(lst):
    """
    Iterate over pairs in the list
    """
    return itertools.izip(lst[::2], lst[1::2])


def update_status(status, multi_key, value):
    if len(multi_key) > 1:
        update_status(status.setdefault(multi_key[0], {}), multi_key[1:], value)
    else:
        status[multi_key[0]] = value


class AddressWizard:
    def __init__(self):
        self.lookup_fn = socket.getaddrinfo
        self.socket_class = socket.socket

    def resolve(self, address_str, do_test=False, explicit_port=False):
        """

        :param address_str:
        :return: tuple of boolean, string, int - isIPv6, resolved_ip, port (may be null), extracted_address
        """

        if not address_str:
            raise RuntimeError("Mandatory option was not specified: address")

        logger.debug("Trying to resolve address string: %s", address_str)

        port = None

        braceport_pat = "^\[([^]]+)\]:(\d+)$"
        braceonly_pat = "^\[([^]]+)\]$"
        if re.match(braceport_pat, address_str):
            logger.debug("Braces and port present")
            match = re.match(braceport_pat, address_str)
            logger.debug("Match: %s %s ", match.group(1), match.group(2))
            address_str, port = match.group(1), match.group(2)
        elif re.match(braceonly_pat, address_str):
            logger.debug("Braces only present")
            match = re.match(braceonly_pat, address_str)
            logger.debug("Match: %s", match.group(1))
            address_str = match.group(1)
        else:
            logger.debug("Parsing port")
            parts = address_str.split(":")
            if len(parts) <= 2:  # otherwise it is v6 address
                address_str = parts[0]
                if len(parts) == 2:
                    port = int(parts[1])
        if port is not None:
            port = int(port)
        try:
            resolved = self.lookup_fn(address_str, port)
            logger.debug("Lookup result: %s", resolved)
        except Exception as exc:
            logger.debug(
                "Exception trying to resolve hostname %s : %s", address_str,
                traceback.format_exc(exc))
            msg = "Failed to resolve hostname: %s. Error: %s"
            raise RuntimeError(msg % (address_str, exc))

        for (family, socktype, proto, canonname, sockaddr) in resolved:
            is_v6 = family == socket.AF_INET6
            parsed_ip, port = sockaddr[0], sockaddr[1]

            if explicit_port:
                logger.warn(
                    "Using phantom.port option is deprecated. Use phantom.address=[address]:port instead"
                )
                port = int(explicit_port)
            elif not port:
                port = 80

            if do_test:
                try:
                    self.__test(family, (parsed_ip, port))
                except RuntimeError as exc:
                    logger.warn(
                        "Failed TCP connection test using [%s]:%s", parsed_ip,
                        port)
                    continue

            return is_v6, parsed_ip, int(port), address_str

        msg = "All connection attempts failed for %s, use phantom.connection_test=0 to disable it"
        raise RuntimeError(msg % address_str)

    def __test(self, af, sa):
        test_sock = self.socket_class(af)
        try:
            test_sock.settimeout(5)
            test_sock.connect(sa)
        except Exception as exc:
            logger.debug(
                "Exception on connect attempt [%s]:%s : %s", sa[0], sa[1],
                traceback.format_exc(exc))
            msg = "TCP Connection test failed for [%s]:%s, use phantom.connection_test=0 to disable it"
            raise RuntimeError(msg % (sa[0], sa[1]))
        finally:
            test_sock.close()


class Chopper(object):
    def __init__(self, source):
        self.source = source

    def __iter__(self):
        for chunk in self.source:
            for item in chunk:
                yield item
