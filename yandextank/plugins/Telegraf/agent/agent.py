#!/usr/bin/env python3
""" The agent bundle, contains all metric classes and agent running code """
import subprocess
import logging
import os
import sys
import signal
import configparser
import json
import threading
import time

from argparse import ArgumentParser
import queue as q

logger = logging.getLogger("agent")
collector_logger = logging.getLogger("telegraf")


def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    logger.warning("Got signal %s, going to stop", sig)
    raise KeyboardInterrupt()


def ignore_handler(sig, frame):
    logger.warning("Got signal %s, ignoring", sig)


def set_sig_handler():
    uncatchable = ['SIG_DFL', 'SIGSTOP', 'SIGKILL']
    ignore = ['SIGCHLD', 'SIGCLD']
    all_sig = [s for s in dir(signal) if s.startswith("SIG")]
    for sig_name in ignore:
        try:
            sig_num = getattr(signal, sig_name)
            signal.signal(sig_num, ignore_handler)
        except Exception:
            pass
    for sig_name in [s for s in all_sig if s not in (uncatchable + ignore)]:
        try:
            sig_num = getattr(signal, sig_name)
            signal.signal(sig_num, signal_handler)
        except Exception as ex:
            logger.error("Can't set handler for %s, %s", sig_name, ex)


class DataReader(object):
    """generator reads from source line-by-line"""

    def __init__(self, filename, pipe=False):
        self.buffer = ""
        self.closed = False
        self.broken = False
        self.pipe = pipe

        if not self.pipe:
            try:
                self.monout = open(filename, 'rb')
            except Exception:
                logger.error("Can't open source file %s: %s", filename, exc_info=True)
                self.broken = True
        else:
            self.monout = filename

    def __iter__(self):
        while not self.closed:
            if self.broken:
                data = ''
            else:
                data = self.monout.readline().decode('utf8')
            if data:
                parts = data.rsplit('\n', 1)
                if len(parts) > 1:
                    ready_chunk = self.buffer + parts[0] + '\n'
                    self.buffer = parts[1]
                    yield ready_chunk
                else:
                    self.buffer += parts[0]
            else:
                yield None
        if not self.pipe:
            self.monout.close()

    def close(self):
        self.closed = True


class Consolidator(object):
    """generator consolidates data from source, cache it by timestamp"""

    def __init__(self, sources):
        self.sources = sources
        self.results = {}

    def append_chunk(self, source, chunk):
        try:
            data = json.loads(chunk)
        except ValueError:
            logger.error('unable to decode chunk %s', chunk, exc_info=True)
        else:
            try:
                ts = data['timestamp']
                self.results.setdefault(ts, {})
                for key, value in data['fields'].items():
                    if data['name'] == 'diskio':
                        data['name'] = "{metric_name}-{disk_id}".format(
                            metric_name=data['name'],
                            disk_id=data['tags']['name'])
                    elif data['name'] == 'net':
                        data['name'] = "{metric_name}-{interface}".format(
                            metric_name=data['name'],
                            interface=data['tags']['interface'])
                    elif data['name'] == 'cpu':
                        data['name'] = "{metric_name}-{cpu_id}".format(
                            metric_name=data['name'],
                            cpu_id=data['tags']['cpu'])
                    key = data['name'] + "_" + key
                    if key.endswith('_exec_value'):
                        key = key.replace('_exec_value', '')
                    self.results[ts][key] = value
            except KeyError:
                logger.error(
                    'Malformed json from source %s: %s',
                    source,
                    chunk,
                    exc_info=True)
            except BaseException:
                logger.error(
                    'Something nasty happend in consolidator work',
                    exc_info=True)

    def __iter__(self):
        while True:
            for s in self.sources:
                chunk_limit = 10
                chunks_done = 0
                chunk = next(s)
                while chunk and chunks_done < chunk_limit:
                    self.append_chunk(s, chunk)
                    chunk = next(s)
                if len(self.results) > 2:
                    logger.debug(
                        'Now in buffer: %s', list(self.results.keys()))
                    dump_seconds = sorted(
                        list(self.results.keys()))[:-2]
                    for ready_second in dump_seconds:
                        yield json.dumps({
                            ready_second: self.results.pop(ready_second, None)
                        })
                time.sleep(0.5)


class Drain(threading.Thread):
    """
    Drain a generator to a destination that answers to put(), in a thread
    """

    def __init__(self, source, destination):
        super(Drain, self).__init__()
        self.source = source
        self.destination = destination
        self._finished = threading.Event()
        self._interrupted = threading.Event()

    def run(self):
        for item in self.source:
            self.destination.put(item)
            if self._interrupted.is_set():
                break
        self._finished.set()

    def wait(self, timeout=None):
        self._finished.wait(timeout=timeout)

    def close(self):
        self._interrupted.set()


class AgentWorker(threading.Thread):
    def __init__(self, telegraf_path):
        super(AgentWorker, self).__init__()
        self.working_dir = os.path.dirname(__file__)
        self.startups = []
        self.startup_processes = []
        self.shutdowns = []
        self.custom_sources = []
        self.daemon = True  # Thread auto-shutdown
        self.finished = False
        self.drain = None
        self.drain_stdout = None
        self.drain_err = None
        self.data_reader = None
        self.telegraf_path = telegraf_path
        self.results = q.Queue()
        self.results_stdout = q.Queue()
        self.results_err = q.Queue()

    @staticmethod
    def __popen(cmnd, shell=False):
        logger.info('Starting telegraf binary:\n{}'.format(' '.join(cmnd)))
        return subprocess.Popen(
            cmnd,
            bufsize=0,
            preexec_fn=os.setsid,
            close_fds=True,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE, )

    def read_startup_config(self, cfg_file='agent_startup.cfg'):
        try:
            config = configparser.RawConfigParser(strict=False)
            with open(os.path.join(self.working_dir, cfg_file), 'r') as f:
                config.read_file(f)

            if config.has_section('startup'):
                for option in config.options('startup'):
                    if option.startswith('cmd'):
                        self.startups.append(config.get('startup', option))

            if config.has_section('shutdown'):
                for option in config.options('shutdown'):
                    if option.startswith('cmd'):
                        self.shutdowns.append(config.get('shutdown', option))

            if config.has_section('source'):
                for option in config.options('source'):
                    if option.startswith('file'):
                        self.custom_sources.append(
                            config.get('source', option))
            logger.info(
                'Successfully loaded startup config.\n'
                'Startups: %s\n'
                'Shutdowns: %s\n', self.startups, self.shutdowns)
        except BaseException:
            logger.error(
                'Error trying to read agent startup config', exc_info=True)

    def run(self):
        logger.info("Running startup commands")
        for cmnd in self.startups:
            logger.debug("Run: %s", cmnd)
            # fixme: shell=True is insecure, should save startup script and
            # launch directly
            proc = self.__popen(cmnd, shell=True)
            logger.info('Started with pid %d', proc.pid)
            self.startup_processes.append(proc)

        logger.info('Starting metrics collector..')
        # todo: add identificators into {} for python 2.6
        args = [self.telegraf_path, '-config',
                '{0}/agent.cfg'.format(self.working_dir)]
        self.collector = self.__popen(cmnd=args)
        logger.info('Started with pid %d', self.collector.pid)

        telegraf_output = self.working_dir + '/monitoring.rawdata'
        sources = [telegraf_output] + self.custom_sources

        for _ in range(10):
            self.collector.poll()
            if not self.collector.returncode:
                logger.info("Waiting for telegraf...")
            else:
                logger.info(
                    "Telegraf with pid %d ended with code %d",
                    self.collector.pid, self.collector.returncode)
            if os.path.isfile(telegraf_output):
                break
            time.sleep(1)

        self.drain = Drain(
            Consolidator([iter(DataReader(f)) for f in sources]), self.results)
        self.drain.start()

        self.drain_stdout = Drain(
            DataReader(
                self.collector.stdout, pipe=True), self.results_stdout)
        self.drain_stdout.start()

        self.drain_err = Drain(
            DataReader(
                self.collector.stderr, pipe=True), self.results_err)
        self.drain_err.start()

        while not self.finished:
            for _ in range(self.results.qsize()):
                try:
                    data = self.results.get_nowait()
                    logger.debug(
                        'send %s bytes of data to collector', len(data))
                    sys.stdout.write(str(data) + '\n')
                    sys.stdout.flush()
                except q.Empty:
                    break
                except BaseException:
                    logger.error(
                        'Something nasty happend trying to send data',
                        exc_info=True)
            for _ in range(self.results_stdout.qsize()):
                try:
                    data = self.results_stdout.get_nowait()
                    if data:
                        collector_logger.info("STDOUT: %s", data)
                except q.Empty:
                    break
            for _ in range(self.results_err.qsize()):
                try:
                    data = self.results_err.get_nowait()
                    if data:
                        collector_logger.info("STDERR: %s", data.rstrip('\n'))
                except q.Empty:
                    break
            time.sleep(1)

        self.drain.close()
        self.drain_stdout.close()
        self.drain_err.close()
        self.stop()

    @staticmethod
    def proc_stop(proc, kill=False):
        proc.poll()
        if proc.returncode is None:
            try:
                if kill:
                    logger.info("Killing PID %s", proc.pid)
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    logger.debug("Terminating: %s", proc.pid)
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait()
                    logger.info(
                        'Retcode for PID %s %s', proc.pid, proc.returncode)
            except OSError as ex:
                if ex.errno == 3:
                    logger.info("PID %s already died", proc.pid)

    def kill(self):
        logger.info("Forced stop")
        for proc in self.startup_processes:
            self.proc_stop(proc, kill=True)
        self.proc_stop(self.collector, kill=True)

    def stop(self):
        logger.info("Terminating startup commands")
        for proc in self.startup_processes:
            self.proc_stop(proc)

        logger.info('Terminating collector process: %s', self.collector)
        self.proc_stop(self.collector)

        logger.info("Running shutdown commands")
        for cmnd in self.shutdowns:
            logger.debug("Run: %s", cmnd)
            subprocess.call(cmnd, shell=True)

        self.finished = True
        logger.info("Worker thread finished")
        sys.stderr.write('stopped\n')


def kill_old_agents(telegraf_path):
    my_pid = os.getpid()
    parent = os.getppid()
    logger.info('My pid: {0} Parent pid: {1}'.format(my_pid, parent))
    ps_output = subprocess.check_output(['ps', 'aux'])
    for line in ps_output.splitlines():
        if telegraf_path in line:
            pid = int(line.split()[1])
            logger.info('Found pid: {0}'.format(pid))
            if pid not in [my_pid, parent]:
                logger.info('Killing process {0}:\n{1}'.format(pid, line))
                os.kill(pid, signal.SIGKILL)


def main():
    fname = os.path.dirname(__file__) + "/_agent.log"
    logging.basicConfig(
        level=logging.DEBUG,
        filename=fname,
        format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s')

    parser = ArgumentParser()
    parser.add_argument(
        "--telegraf",
        dest="telegraf_path",
        help="telegraf_path",
        default="/tmp/telegraf")
    parser.add_argument(
        "--host",
        dest="hostname_path",
        help="telegraf_path",
        default="/usr/bin/telegraf")
    parser.add_argument(
        "-k", "--kill-old",
        action="store_true",
        dest="kill_old"
    )
    options = parser.parse_args()

    logger.info('Init')
    customs_script = os.path.dirname(__file__) + '/agent_customs.sh'
    # todo: deprecate
    if options.kill_old:
        kill_old_agents(options.telegraf_path)

    try:
        logger.info(
            'Trying to make telegraf executable: %s', options.telegraf_path)
        # 0o755 compatible with old python versions. 744 is NOT enough
        os.chmod(options.telegraf_path, 493)
    except OSError:
        logger.warning(
            'Unable to set %s access rights to execute.',
            options.telegraf_path,
            exc_info=True)
    try:
        logger.info(
            'Trying to make customs script executable: %s', customs_script)
        # 0o755 compatible with old python versions. 744 is NOT enough
        os.chmod(customs_script, 493)
    except OSError:
        logger.warning(
            'Unable to set %s access rights to execute.',
            customs_script,
            exc_info=True)

    worker = AgentWorker(options.telegraf_path)
    worker.read_startup_config()

    logger.info('Starting AgentWorker: %s', worker)
    worker.start()

    try:
        logger.debug("Check for any stdin command for shutdown")
        cmd = sys.stdin.readline()
        if cmd:
            logger.info("Stdin cmd received: %s", cmd)
    except KeyboardInterrupt:
        logger.debug("Interrupted")
    except BaseException:
        logger.error(
            "Something nasty happened while waiting for stop", exc_info=True)
    worker.finished = True
    agent_finished = False
    while not agent_finished:
        try:
            if worker.isAlive():
                logger.debug("Join the worker thread, waiting for cleanup")
                worker.join(10)
            if worker.isAlive():
                logger.error(
                    "Worker have not finished shutdown in 10 seconds, going to exit anyway"
                )
                worker.kill()
                agent_finished = True
            else:
                agent_finished = True
        except BaseException:
            logger.info(
                "Something nasty happened while waiting for worker shutdown",
                exc_info=True)


if __name__ == '__main__':
    set_sig_handler()
    main()
