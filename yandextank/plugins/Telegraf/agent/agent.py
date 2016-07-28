#! /usr/bin/env python2
""" The agent bundle, contains all metric classes and agent running code """
import subprocess
import logging
import os
import sys
import signal
from threading import Thread
import ConfigParser
import json
from optparse import OptionParser
import time

logger = logging.getLogger(__name__)
collector_logger = logging.getLogger("telegraf")

def signal_handler(sig, frame):
    """ required for non-tty python runs to interrupt """
    raise KeyboardInterrupt()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class DataReader(object):
    """geneartor drains a source
    source should be file-like object and support readline()
    """
    def __init__(self, pipe):
        self.source = pipe

    def __iter__(self):
        while True:
            data = self.source.readline().strip('\n')
            if data:
                yield data


class DataAggregator(object):
    """aggregate monitoring chunks"""
    def __init__(self):
        self.buffer = ""
        self.prev_ts = None
        self.result = {}
        self.prev_ts = None
        self.buffer = ""

    def aggregate(self, chunk):
        if self.buffer or chunk:
            try:
                result_buffer = {}
                if self.buffer:
                    jsn = json.loads(self.buffer)
                    self.buffer = ""
                else:
                    jsn = json.loads(chunk)
                ts = str(jsn['timestamp'])
                if ts == self.prev_ts:
                    self.result.setdefault(ts, {})
                    for key, value in jsn['fields'].iteritems():
                        key = jsn['name']+"_"+key
                        self.result[ts][key] = value
                else:
                    self.prev_ts = ts
                    result_buffer = self.result
                    self.result = {}
                    self.buffer = chunk
                if result_buffer:
                    return json.dumps(result_buffer)
            except ValueError:
                logger.error('Unable to decode json: %s', chunk, exc_info=True)
            except:
                logger.error('Exception aggreagating chunks', exc_info=True)


class AgentWorker(Thread):
    def __init__(self, telegraf_path):
        Thread.__init__(self)
        self.working_dir = os.path.dirname(__file__)
        self.startups = []
        self.startup_processes = []
        self.shutdowns = []
        self.daemon = True  # Thread auto-shutdown
        self.finished = False
        self.telegraf_path = telegraf_path
        self.aggregator = DataAggregator()
        self.stdout_reader = None

    @staticmethod
    def popen(cmnd):
        return subprocess.Popen(
            cmnd,
            bufsize=0,
            preexec_fn=os.setsid,
            close_fds=True,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

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
                'Shutdowns: %s\n', self.startups, self.shutdowns
            )
        except:
            logger.error('Error trying to read agent startup config', exc_info=True)

    def run(self):
        logger.info("Running startup commands")
        for cmnd in self.startups:
            logger.debug("Run: %s", cmnd)
            proc = self.popen(cmnd)
            self.startup_processes.append(proc)

        logger.info('Starting metrics collector..')
        cmnd = "{telegraf} -config {working_dir}/agent.cfg".format(
            telegraf=self.telegraf_path,
            working_dir=self.working_dir
        )
        self.collector = self.popen(cmnd)
        self.stdout_reader = DataReader(self.collector.stdout)
        while not self.finished:
            try:
                for stdout_data in self.stdout_reader:
                    aggregate_result = self.aggregator.aggregate(stdout_data)
                    if aggregate_result:
                        logger.debug('aggregated ts : %s', aggregate_result)
                        sys.stdout.write(str(aggregate_result)+'\n')
                for stderr_data in DataReader(self.collector.stderr):
                    logger.error('Stderr message: %s', stderr_data)
            except:
                logger.error('Unknown exception reading monitoring agent data', exc_info=True)
        logger.debug('Telegraf finished')
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


if __name__ == '__main__':
    fname = os.path.dirname(__file__) + "/_agent.log"
    fmt = "%(asctime)s - %(filename)s - %(name)s - %(levelname)s - %(message)s"
    logging.basicConfig(filename=fname, level=logging.DEBUG, format=fmt)

    parser = OptionParser()
    parser.add_option("", "--telegraf", dest="telegraf_path",
                  help="telegraf_path", default="/tmp/telegraf")
    parser.add_option("", "--host", dest="hostname_path",
                  help="telegraf_path", default="/usr/bin/telegraf")
    (options, args) = parser.parse_args()


    logger.info('Init')
    try:
        logger.info('Trying to make telegraf executable')
        os.chmod(options.telegraf_path, 0744)
    except OSError:
        logger.warning('Unable to set %s access rights to execute.', options.telegraf_path, exc_info=True)

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