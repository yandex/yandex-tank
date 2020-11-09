import queue
import hashlib
import logging
import os
import subprocess
import tempfile
import threading
import time
from shutil import copyfile, rmtree
from ...common.util import SecuredShell

from ..Telegraf.config import AgentConfig, create_agent_py
from ..Telegraf.reader import MonitoringReader

logger = logging.getLogger(__name__)
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)


def generate_file_md5(filename, blocksize=2 ** 20):
    m = hashlib.md5()
    with open(filename, "rb") as f:
        while True:
            buf = f.read(blocksize)
            if not buf:
                break
            m.update(buf)
    return m.hexdigest()


class LocalhostClient(object):
    """ localhost client setup """
    AGENT_FILENAME = 'agent.py'

    def __init__(self, config, old_style_configs, kill_old):
        # config
        self.kill_old = '--kill-old' if kill_old else ''
        self.python = config['python']
        self.host = "localhost"
        self.telegraf = config['telegraf']
        self.config = AgentConfig(config, old_style_configs)

        # connection
        self.incoming_queue = queue.Queue()
        self.buffer = ""

        self.workdir = None
        self.reader = MonitoringReader(self.incoming_queue)

        self.path = {
            'AGENT_LOCAL_PATH': create_agent_py(self.AGENT_FILENAME),
            'TELEGRAF_LOCAL_PATH': self.telegraf,
        }

    def install(self):
        self.workdir = tempfile.mkdtemp()
        logger.info("Created temp dir %s", self.workdir)
        agent_config = self.config.create_collector_config(self.workdir)
        startup_config = self.config.create_startup_config()
        customs_script = self.config.create_custom_exec_script()
        try:
            copyfile(
                self.path['AGENT_LOCAL_PATH'],
                os.path.join(
                    self.workdir,
                    self.AGENT_FILENAME))
            copyfile(agent_config, os.path.join(self.workdir, 'agent.cfg'))
            copyfile(startup_config, os.path.join(
                self.workdir,
                'agent_startup.cfg'))
            copyfile(
                customs_script,
                os.path.join(
                    self.workdir,
                    'agent_customs.sh'))
            if not os.path.isfile(self.path['TELEGRAF_LOCAL_PATH']):
                logger.error(
                    'Telegraf binary not found at specified path: %s\n'
                    'You can find telegraf binaries here: https://github.com/influxdata/telegraf\n'
                    'or install debian package: `telegraf`',
                    self.path['TELEGRAF_LOCAL_PATH'])
                return None, None, None
        except Exception:
            logger.error("Failed to copy agent to %s on localhost", self.workdir)
            logger.debug("Failed to copy agent to %s on localhost", self.workdir, exc_info=True)
            return None, None, None
        return agent_config, startup_config, customs_script

    @staticmethod
    def popen(args):
        return subprocess.Popen(
            args,
            bufsize=0,
            preexec_fn=os.setsid,
            close_fds=True,
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE, )

    def start(self):
        """Start local agent"""
        args = self.python.split() + [
            os.path.join(
                self.workdir,
                self.AGENT_FILENAME),
            '--telegraf',
            self.path['TELEGRAF_LOCAL_PATH'],
            '--host',
            self.host]
        if self.kill_old:
            args.append(self.kill_old)
        logger.info('Starting agent on localhost: {}'.format(args))
        self.session = self.popen(args)
        self.reader_thread = threading.Thread(target=self.read_buffer)
        self.reader_thread.setDaemon(True)
        return self.session

    def read_buffer(self):
        while self.session:
            try:
                chunk = self.session.stdout.read(4096).decode('utf8')
                if chunk:
                    parts = chunk.rsplit('\n', 1)
                    if len(parts) > 1:
                        ready_chunk = self.buffer + parts[0] + '\n'
                        self.buffer = parts[1]
                        self.incoming_queue.put(ready_chunk)
                    else:
                        self.buffer += parts[0]
            except ValueError:
                logger.debug(
                    'this exc most likely raised during interpreter shutdown\n'
                    'otherwise something really nasty happend',
                    exc_info=True)

    def _stop_agent(self):
        if self.session:
            self.session.terminate()
            logger.info('Waiting localhost agent to terminate...')

    def uninstall(self):
        """
        Remove agent's files from remote host
        """
        if self.session:
            self.session.wait()
            self.session = None
        log_filename = "agent_{host}.log".format(host="localhost")
        data_filename = "agent_{host}.rawdata".format(host="localhost")
        try:
            logger.info('Saving monitoring artifacts from localhost')
            copyfile(self.workdir + "/_agent.log", log_filename)
            copyfile(self.workdir + "/monitoring.rawdata", data_filename)
            logger.info('Deleting temp directory: %s', self.workdir)
            rmtree(self.workdir)
        except Exception:
            logger.error("Exception while uninstalling agent", exc_info=True)

        logger.info("Removing agent from: localhost")
        return log_filename, data_filename


class SSHClient(object):
    """remote agent client setup """
    AGENT_FILENAME = 'agent.py'

    def __init__(self, config, old_style_configs, timeout, kill_old):
        # config
        self.kill_old = '--kill-old' if kill_old else ''
        self.host = config['host']
        self.username = config['username']
        self.python = config['python']
        self.port = config['port']
        self.telegraf = config['telegraf']
        self.config = AgentConfig(config, old_style_configs)

        # connection
        self.session = None
        self.ssh = SecuredShell(self.host, self.port, self.username, timeout)
        self.incoming_queue = queue.Queue()
        self.buffer = ""
        self.stop_sent = None
        self.successfull_stop = None

        self.reader = MonitoringReader(self.incoming_queue)
        handle, cfg_path = tempfile.mkstemp('.cfg', 'agent_')
        os.close(handle)
        self.path = {
            # Destination path on remote host
            'AGENT_REMOTE_FOLDER': '/tmp/',
            # Source path on tank
            'AGENT_LOCAL_PATH': create_agent_py(self.AGENT_FILENAME),
            'TELEGRAF_REMOTE_PATH': '/tmp/telegraf',
            'TELEGRAF_LOCAL_PATH': self.telegraf,
        }
        self.agent_remote_folder = None

    def install(self):
        """Create folder and copy agent and metrics scripts to remote host"""
        logger.info(
            "Installing monitoring agent at %s@%s...",
            self.username,
            self.host)

        # create remote temp dir
        cmd = self.python + ' -c "import tempfile; print(tempfile.mkdtemp());"'
        logger.info("Creating temp dir on %s", self.host)
        try:
            out, errors, err_code = self.ssh.execute(cmd)
        except Exception:
            logger.error(
                "Failed to install monitoring agent to %s",
                self.host,
                exc_info=True)
            return None, None, None
        if errors:
            logger.error("[%s] error: '%s'", self.host, errors)
            logger.error("Cancelling agent installation on %s", self.host)
            return None, None, None

        if err_code:
            logger.error(
                "Failed to create remote dir via SSH at %s@%s, code %s: %s" %
                (self.username, self.host, err_code, out.strip()))
            return None, None, None

        remote_dir = out.strip()
        if remote_dir:
            self.path['AGENT_REMOTE_FOLDER'] = remote_dir
            self.agent_remote_folder = remote_dir
        logger.debug(
            "Remote dir at %s:%s", self.host, self.path['AGENT_REMOTE_FOLDER'])

        # create collector config
        agent_config = self.config.create_collector_config(
            self.path['AGENT_REMOTE_FOLDER'])
        startup_config = self.config.create_startup_config()
        customs_script = self.config.create_custom_exec_script()

        # trying to detect os version/architecture and get information about telegraf client
        # DO NOT DELETE indices in string format below. Python 2.6 does not
        # support string formatting without indices
        remote_cmd = 'import os; print os.path.isfile("' + self.path[
            'TELEGRAF_REMOTE_PATH'] + '")'
        cmd = self.python + ' -c \'{cmd}\''.format(cmd=remote_cmd)
        remote_telegraf_exists = "False"
        try:
            out, err, err_code = self.ssh.execute(cmd)
        except Exception:
            logger.error(
                "SSH execute error trying to check telegraf availability on host %s",
                self.host,
                exc_info=True)
        else:
            if err:
                logger.error("[%s] error: '%s'", self.host, errors)
            if out.strip():
                remote_telegraf_exists = out.strip()

        try:
            if remote_telegraf_exists in "True":
                logger.debug('Found telegraf client on %s..', self.host)
            else:
                logger.debug(
                    'Not found telegraf client on %s, trying to install from tank. Copying..',
                    self.host)
                if os.path.isfile(self.path['TELEGRAF_LOCAL_PATH']):
                    self.ssh.send_file(
                        self.path['TELEGRAF_LOCAL_PATH'],
                        self.path['TELEGRAF_REMOTE_PATH'])
                elif os.path.isfile("/usr/bin/telegraf"):
                    self.ssh.send_file(
                        '/usr/bin/telegraf', self.path['TELEGRAF_REMOTE_PATH'])
                else:
                    logger.error(
                        'Telegraf binary not found neither on %s nor on localhost at specified path: %s\n'
                        'You can find telegraf binaries here: https://github.com/influxdata/telegraf\n'
                        'or install debian package: `telegraf`', self.host, self.path['TELEGRAF_LOCAL_PATH'])
                    return None, None, None

            self.ssh.send_file(
                self.path['AGENT_LOCAL_PATH'],
                os.path.join(
                    self.path['AGENT_REMOTE_FOLDER'],
                    self.AGENT_FILENAME))
            self.ssh.send_file(
                agent_config,
                os.path.join(
                    self.path['AGENT_REMOTE_FOLDER'],
                    'agent.cfg'))
            self.ssh.send_file(
                startup_config,
                os.path.join(
                    self.path['AGENT_REMOTE_FOLDER'],
                    'agent_startup.cfg'))
            self.ssh.send_file(
                customs_script,
                os.path.join(
                    self.path['AGENT_REMOTE_FOLDER'],
                    'agent_customs.sh'))

        except Exception:
            logger.error(
                "Failed to install agent on %s", self.host, exc_info=True)
            return None, None, None

        return agent_config, startup_config, customs_script

    def start(self):
        """Start remote agent"""
        logger.info('Starting agent: %s', self.host)
        command = "{python} {agent_path} --telegraf {telegraf_path} --host {host} {kill_old}".format(
            python=self.python,
            agent_path=os.path.join(
                self.path['AGENT_REMOTE_FOLDER'],
                self.AGENT_FILENAME),
            telegraf_path=self.path['TELEGRAF_REMOTE_PATH'],
            host=self.host,
            kill_old=self.kill_old)
        logger.debug('Command to start agent: %s', command)
        self.session = self.ssh.async_session(command)
        self.reader_thread = threading.Thread(target=self.read_buffer)
        self.reader_thread.setDaemon(True)
        return self.session

    def read_buffer(self):
        while self.session and not self.stop_sent:
            chunk = self.session.read_maybe()
            if chunk:
                parts = chunk.rsplit('\n', 1)
                if len(parts) > 1:
                    ready_chunk = self.buffer + parts[0] + '\n'
                    self.buffer = parts[1]
                    self.incoming_queue.put(ready_chunk)
                else:
                    self.buffer += parts[0]
            else:
                time.sleep(1)
        logger.info('Daemon reader stopped')

    def _stop_agent(self):
        """
        Stop data collection. Separated from uninstall to speed up multihost processing
        """

        try:
            if self.session:
                self.session.send("stop\n")
                self.stop_sent = time.time()
        except BaseException:
            logger.warning(
                'Unable to correctly stop monitoring agent - session is broken on %s.',
                self.host,
                exc_info=True)

    def uninstall(self):
        """
        Remove agent's files from remote host
        """
        log_filename = "agent_{host}.log".format(host=self.host)
        data_filename = "agent_{host}.rawdata".format(host=self.host)

        try:
            if self.session:
                self._wait_for_stop()
                self.session.close()
                self.session = None
        except BaseException:
            logger.warning(
                'Unable to correctly stop monitoring agent - session is broken. Pay attention to agent log (%s).',
                log_filename,
                exc_info=True)
        try:
            self.ssh.get_file(
                os.path.join(
                    self.path['AGENT_REMOTE_FOLDER'],
                    "_agent.log"),
                log_filename)
            self.ssh.get_file(
                os.path.join(
                    self.path['AGENT_REMOTE_FOLDER'],
                    "monitoring.rawdata"),
                data_filename)
            self.ssh.rm_r(self.path['AGENT_REMOTE_FOLDER'])
        except Exception:
            logger.error("Unable to get agent artefacts", exc_info=True)
        if not self.successfull_stop:
            self._kill_agent()
        return log_filename, data_filename

    def _wait_for_stop(self):
        done = False
        agent_stop_timeout = 5
        while not done:
            if not self.stop_sent:
                logger.info('Session was broken on %s, switch to kill', self.host)
                break
            if (self.stop_sent + agent_stop_timeout) < time.time():
                logger.info("Agent hasn't finished in %s sec, force quit on %s",
                            agent_stop_timeout,
                            self.host)
                break
            if self.session.finished():
                logger.debug('Session ended with status %s with %s',
                             self.session.exit_status(),
                             self.host)
                self.successfull_stop = True
                done = True
            agent_stderr = self.session.read_err_maybe()
            if agent_stderr and 'stopped' in agent_stderr:
                logger.debug('Got stopped message from %s', self.host)
                done = True

    def _kill_agent(self):
        if self.agent_remote_folder:
            tpl = ('main_p=$(pgrep -f "[p]ython.*{folder}");'
                   'tlgrf_p=$(pgrep -f "[t]elegraf.*{folder}");'
                   'descendent_pids(){{ if [ "x$1" != "x" ]; then '
                   'pids=$(pgrep -P $1); echo $pids;'
                   'for p in $pids; do descendent_pids $p; done; fi }};'
                   'all_p=$(descendent_pids ${{main_p}});'
                   'if [ "x${{main_p}}${{tlgrf_p}}${{all_p}}" != "x" ] ; then '
                   ' kill -9 ${{main_p}} ${{tlgrf_p}} ${{all_p}}; fi')
            cmd = tpl.format(folder=self.agent_remote_folder)
            out, errors, err_code = self.ssh.execute(cmd)
            if errors:
                logger.error(
                    "[%s] error while killing agent: '%s'",
                    self.host,
                    errors)
