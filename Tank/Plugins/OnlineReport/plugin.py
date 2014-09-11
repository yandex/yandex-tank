''' local webserver with online graphs '''
from threading import Thread
import json
import logging
import os.path
import time
import socket

from Tank.Plugins.Monitoring import MonitoringPlugin
from Tank.MonCollector.collector import MonitoringDataListener

from Tank.Plugins.Aggregator import AggregatorPlugin, AggregateResultListener
from tankcore import AbstractPlugin
import tankcore

from server import ReportServer
from decode import decode_aggregate, decode_monitoring

class OnlineReportPlugin(AbstractPlugin, Thread, AggregateResultListener):
    ''' web online plugin '''
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
        self.quantiles_data = []
        self.codes_data = []
        self.avg_data = []

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
            self.server = ReportServer()
            self.server.owner = self
        except Exception, ex:
            self.log.warning("Failed to start web results server: %s", ex)


    def start_test(self):
        self.start()


    def end_test(self, retcode):
        del self.server
        self.server = None
        return retcode


    def run(self):
        if (self.server):
            address = socket.gethostname()
            self.log.info("Starting local HTTP server for online view at port: http://%s:%s/", address, self.port)
            self.server.serve()


    def aggregate_second(self, data):
        if self.server is not None:
            data = decode_aggregate(data)
            self.server.send(json.dumps(data))

    def monitoring_data(self, data):
        data = decode_monitoring(data)
        if self.server is not None and len(data):
            self.server.send(json.dumps(data))
