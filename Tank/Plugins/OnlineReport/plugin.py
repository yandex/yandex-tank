''' local webserver with online graphs '''
from threading import Thread
import logging
import os.path
import time
import socket
import requests

from Tank.Plugins.Monitoring import MonitoringPlugin
from Tank.MonCollector.collector import MonitoringDataListener

from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener
from tankcore import AbstractPlugin
import tankcore

from server import ReportServer
from decode import decode_aggregate, decode_monitoring

from cache import DataCacher

class OnlineReportPlugin(AbstractPlugin, Thread, AggregateResultListener):
    '''Interactive report plugin '''
    SECTION = "web"

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        Thread.__init__(self)
        self.daemon = True  # Thread auto-shutdown
        self.port = 8080
        self.last_sec = None
        self.server = None
        self.cache = DataCacher()

    def get_available_options(self):
        return ["port"]

    def configure(self):
        self.port = int(self.get_option("port", self.port))
        try:
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(self)
        except KeyError:
            self.log.warning("No aggregator module, no valid report will be available")

        try:
            mon = self.core.get_plugin_of_type(MonitoringPlugin)
            if mon.monitoring:
                mon.monitoring.add_listener(self)
        except KeyError:
            self.log.warning("No monitoring module, monitroing report disabled")

    def prepare_test(self):
        try:
            self.server = ReportServer(self.cache)
            self.server.owner = self
        except Exception, ex:
            self.log.warning("Failed to start web results server: %s", ex)


    def start_test(self):
        self.start()


    def end_test(self, retcode):
        self.server.reload()
        return retcode


    def run(self):
        if (self.server):
            address = socket.gethostname()
            self.log.info("Starting local HTTP server for online view at port: http://%s:%s/", address, self.port)
            self.server.serve()
            self.server.reload()


    def aggregate_second(self, data):
        data = decode_aggregate(data)
        self.cache.store(data)
        if self.server is not None:
            message = {
                'data': data,
            }
            self.server.send(message)

    def monitoring_data(self, data):
        data = decode_monitoring(data)
        self.cache.store(data)
        if self.server is not None and len(data):
            message = {
                'data': data,
            }
            self.server.send(message)

    def post_process(self, retcode):
        self.log.info("Building HTML report...")
        report_html = self.core.mkstemp(".html", "report_")
        self.core.add_artifact_file(report_html)
        with open(report_html, 'w') as report_html_file:
            report_html_file.write(
                requests.get('http://localhost:8001/offline.html').text
            )
        raw_input('Press Enter to stop report server.')
        del self.server
        self.server = None
        return retcode
