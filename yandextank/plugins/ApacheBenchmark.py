''' AB load generator '''
from Aggregator import AggregatorPlugin, AbstractReader
from ConsoleOnline import ConsoleOnlinePlugin, AbstractInfoWidget

import os
import subprocess

from yandextank.core import AbstractPlugin
import yandextank.core as tankcore

class ApacheBenchmarkPlugin(AbstractPlugin):
    ''' Apache Benchmark plugin '''
    SECTION = 'ab'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.out_file = None
        self.process = None
        self.concurrency = 0
        self.options = None
        self.url = None
        self.requests = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["options", "url", "requests", "concurrency"]

    def configure(self):
        self.options = self.get_option("options", '')
        self.url = self.get_option("url", 'http://localhost/')
        self.requests = self.get_option("requests", '100')
        self.concurrency = self.get_option("concurrency", '1')
        self.out_file = self.core.mkstemp('.log', 'ab_')
        self.core.add_artifact_file(self.out_file)

    def prepare_test(self):
        aggregator = None
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
        except Exception, ex:
            self.log.warning("No aggregator found: %s", ex)

        if aggregator:
            aggregator.reader = ABReader(aggregator, self)

        try:
            console = self.core.get_plugin_of_type(ConsoleOnlinePlugin)
        except Exception, ex:
            self.log.debug("Console not found: %s", ex)
            console = None

        if console:
            widget = ABInfoWidget(self)
            console.add_info_widget(widget)


    def start_test(self):
        args = ['ab', '-r', '-g', self.out_file,
                '-n', self.requests,
                '-c', self.concurrency, self.url]
        self.log.info("Starting ab with arguments: %s", args)
        self.process = subprocess.Popen(args, stderr=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True)

    def is_test_finished(self):
        retcode = self.process.poll()
        if retcode != None:
            self.log.debug("%s exit code: %s", self.SECTION, retcode)
            return retcode
        else:
            return -1


    def end_test(self, retcode):
        if self.process and self.process.poll() is None:
            self.log.warn("Terminating ab process with PID %s", self.process.pid)
            self.process.terminate()
        else:
            self.log.info("Seems ab finished OK")

        if self.process:
            tankcore.log_stdout_stderr(self.log, self.process.stdout, self.process.stderr, self.SECTION)
        return retcode



class ABReader(AbstractReader):
    '''
    Adapter to read AB files
    '''
    def __init__(self, aggregator, abench):
        AbstractReader.__init__(self, aggregator)
        self.abench = abench
        self.results = None

    def check_open_files(self):
        if not self.results and os.path.exists(self.abench.out_file):
            self.log.debug("Opening ab out file: %s", self.abench.out_file)
            self.results = open(self.abench.out_file, 'r')

    def close_files(self):
        if self.results:
            self.results.close()

    def get_next_sample(self, force):
        if self.results:
            read_lines = self.results.readlines()
            if read_lines:
                read_lines.pop(0)  # remove header line
            self.log.debug("About to process %s result lines", len(read_lines))
            for line in read_lines:
                line = line.strip()
                if not line:
                    return None
                # Tue Sep 25 14:19:36 2012        1348568376      0       36      36      34
                data = line.split("\t")
                if len(data) != 6:
                    self.log.warning("Wrong ab log line, skipped: %s", line)
                    continue
                cur_time = int(data[1])
                ctime = int(data[2])
                # dtime = int(data[3])
                ttime = int(data[4])
                wait = int(data[5])

                if not cur_time in self.data_buffer.keys():
                    self.data_queue.append(cur_time)
                    self.data_buffer[cur_time] = []
                #        marker, threads, overallRT, httpCode, netCode
                data_item = ['', self.abench.concurrency, ttime, 0, 0]
                # bytes:     sent    received
                data_item += [0, 0]
                #        connect    send    latency    receive
                data_item += [ctime, 0, wait, ttime - ctime - wait]
                #        accuracy
                data_item += [0]
                self.data_buffer[cur_time].append(data_item)

        if self.data_queue:
            return self.pop_second()
        else:
            return None


class ABInfoWidget(AbstractInfoWidget):
    ''' Console widget '''
    def __init__(self, abench):
        AbstractInfoWidget.__init__(self)
        self.abench = abench
        self.active_threads = 0

    def get_index(self):
        return 0

    def render(self, screen):
        ab_text = " Apache Benchmark Test "
        space = screen.right_panel_width - len(ab_text) - 1
        left_spaces = space / 2
        right_spaces = space / 2
        template = screen.markup.BG_BROWN + '~' * left_spaces + ab_text + ' ' + '~' * right_spaces + screen.markup.RESET + "\n"
        template += "           URL: %s\n"
        template += "   Concurrency: %s\n"
        template += "Total Requests: %s"
        data = (self.abench.url, self.abench.concurrency, self.abench.requests)

        return template % data
