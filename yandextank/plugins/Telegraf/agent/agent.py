#!/usr/bin/env python
""" The agent bundle, contains all metric classes and agent running code """
import subprocess
import logging
import os
import sys
import signal
import ConfigParser
import json
import threading
import time

from optparse import OptionParser
import Queue as q

logger = logging.getLogger("agent")
collector_logger = logging.getLogger("telegraf")


def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    raise KeyboardInterrupt()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class DataReader(object):
    """generator reads from source line-by-line"""

    def __init__(self, filename, pipe=False):
        self.pipe = pipe
        if not self.pipe:
            self.monout = open(filename, 'r')
        else:
            self.monout = filename
        self.buffer = ""
        self.closed = False

    def __iter__(self):
        while not self.closed:
            data = self.monout.readline()
            if data:
                parts = data.rsplit('\n', 1)
                if len(parts) > 1:
                    ready_chunk = self.buffer + parts[0] + '\n'
                    self.buffer = parts[1]
                    yield ready_chunk
                else:
                    self.buffer += parts[0]
            else:
                time.sleep(1)
        if not self.pipe:
            self.monout.close()

    def close(self):
        self.closed = True


class Consolidator(object):
    """generator consolidates data from source, cache it by timestamp"""

    def __init__(self, source):
        self.source = source
        self.results = {}

    def __iter__(self):
        for chunk in self.source:
            if chunk:
                try:
                    data = json.loads(chunk)
                except ValueError:
                    logger.error(
                        'unable to decode chunk %s', chunk, exc_info=True)
                else:
                    try:
                        ts = data['timestamp']
                        self.results.setdefault(ts, {})
                        for key, value in data['fields'].iteritems():
                            if data['name'] == 'diskio':
                                data['name'] = "{metric_name}-{disk_id}".format(
                                    metric_name=data['name'],
                                    disk_id=data['tags']['name'])
                            elif data['name'] == 'net':
                                data[
                                    'name'] = "{metric_name}-{interface}".format(
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
                            'Malformed json from source: %s',
                            chunk,
                            exc_info=True)
                    except:
                        logger.error(
                            'Something nasty happend in consolidator work',
                            exc_info=True)
            if len(self.results) > 5:
                ready_to_go_index = min(self.results)
                yield json.dumps({
                    ready_to_go_index:
                    self.results.pop(ready_to_go_index, None)
                })


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
    def popen(cmnd):
        return subprocess.Popen(
            cmnd,
            bufsize=0,
            preexec_fn=os.setsid,
            close_fds=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE, )

    def read_startup_config(self, cfg_file='agent_startup.cfg'):
        try:
            config = ConfigParser.ConfigParser()
            with open(os.path.join(self.working_dir, cfg_file), 'rb') as f:
                config.readfp(f)

            if config.has_section('startup'):
                for option in config.options('startup'):
                    if option.startswith('cmd'):
                        self.startups.append(config.get('startup', option))

            if config.has_section('shutdown'):
                for option in config.options('shutdown'):
                    if option.startswith('cmd'):
                        self.shutdowns.append(config.get('shutdown', option))
            logger.info(
                'Successfully loaded startup config.\n'
                'Startups: %s\n'
                'Shutdowns: %s\n', self.startups, self.shutdowns)
        except:
            logger.error(
                'Error trying to read agent startup config', exc_info=True)

    def run(self):
        logger.info("Running startup commands")
        for cmnd in self.startups:
            logger.debug("Run: %s", cmnd)
            proc = self.popen(cmnd)
            self.startup_processes.append(proc)

        logger.info('Starting metrics collector..')
        cmnd = "{telegraf} -config {working_dir}/agent.cfg".format(
            telegraf=self.telegraf_path, working_dir=self.working_dir)
        self.collector = self.popen(cmnd)

        telegraf_output = self.working_dir + '/monitoring.rawdata'

        for _ in range(10):
            logger.info("Waiting for telegraf...")
            if os.path.isfile(telegraf_output):
                break
            time.sleep(1)

        self.drain = Drain(
            Consolidator(DataReader(telegraf_output)), self.results)
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
                except q.Empty:
                    break
                except:
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
                        collector_logger.info("STDERR: %s", data)
                except q.Empty:
                    break
            time.sleep(1)

        self.stop()

    def stop(self):
        logger.info("Terminating startup commands")
        for proc in self.startup_processes:
            logger.debug("Terminate: %s", proc)
            os.killpg(proc.pid, signal.SIGTERM)

        logger.info("Running shutdown commands")
        for cmnd in self.shutdowns:
            logger.debug("Run: %s", cmnd)
            subprocess.call(cmnd, shell=True)

        logger.info('Terminating collector process: %s', self.collector)
        if not self.collector.returncode:
            self.collector.terminate()
            self.collector.wait()
        self.finished = True
        sys.stderr.write('stopped\n')
        logger.info('Stopped via stdin')

        logger.info('retcode: %s', self.collector.returncode)

        logger.info("Worker thread finished")


def main():
    fname = os.path.dirname(__file__) + "/_agent.log"
    logging.basicConfig(
        level=logging.DEBUG,
        filename=fname,
        format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s')

    parser = OptionParser()
    parser.add_option(
        "",
        "--telegraf",
        dest="telegraf_path",
        help="telegraf_path",
        default="/tmp/telegraf")
    parser.add_option(
        "",
        "--host",
        dest="hostname_path",
        help="telegraf_path",
        default="/usr/bin/telegraf")
    (options, args) = parser.parse_args()

    logger.info('Init')
    customs_script = os.path.dirname(__file__) + '/agent_customs.sh'
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
            worker.stop()
    except KeyboardInterrupt:
        logger.debug("Interrupted")
        worker.stop()


if __name__ == '__main__':
    main()
