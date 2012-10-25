'''Graphite Uploader plugin that sends aggregated data to Graphite server'''

from Tank.Plugins.Aggregator import AggregateResultListener, AggregatorPlugin
from tankcore import AbstractPlugin
import logging
import socket
import string
import time

class GraphiteUploaderPlugin(AbstractPlugin, AggregateResultListener):
    '''Graphite data uploader'''
    
    SECTION = 'graphite'

    @staticmethod
    def get_key():
        return __file__
    
    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.graphite_client = None

    def configure(self):
        '''Read configuration'''
        address = self.get_option("address", "")
        if address == "": 
            self.log.warning("Graphite uploader is not configured and will not send any data")
        else:
            port = self.get_option("port", "2024")
            prefix = self.get_option("prefix", "one_sec.yandex_tank")
            self.graphite_client = GraphiteClient(prefix, address, port)
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(self)

    def aggregate_second(self, data):
        """
        @data: SecondAggregateData
        """
        if self.graphite_client:
            results = {}
            overall = GraphiteUploaderPlugin.__flatten(data.overall.__dict__, "overall")
            cumulative = GraphiteUploaderPlugin.__flatten(data.cumulative.__dict__, "cumulative")
            results.update(overall)
            results.update(cumulative)
            for case_key in data.cases.keys():
                case_result = GraphiteUploaderPlugin.__flatten(data.cases[case_key].__dict__, str(case_key))
                results.update(case_result)
            self.graphite_client.submit(results)

    @staticmethod
    def __flatten(dic, prefix):
        '''recursively pass through a dict and flatten it\'s "internal" dicts'''
        results = {}
        if dic != None:
            try:
                for key in dic.keys():
                    if type(dic[key]) in [float, int]:
                        results["%s.%s" % (prefix, str(key).translate(string.maketrans(".", "_")))] = dic[key]
                    elif type(dic[key] in [dict]):
                        results.update(GraphiteUploaderPlugin.__flatten(dic[key], "%s.%s" % (prefix, key.translate(string.maketrans(".", "_")))))
            except AttributeError:
                pass
        return results


    
class GraphiteClient(object):
    '''Graphite client that writes metrics to Graphite server'''

    def __init__(self, prefix, address, port):
        self.address = address
        self.port = port
        self.prefix = prefix
        self.log = logging.getLogger(__name__)
        self.log.debug("Created a Graphite listener with address = '%s', port = '%s', prefix = '%s'" % (address, port, prefix))

    def submit(self, results):
        '''publish results to Graphite'''
        self.log.debug("Trying to send metrics to server...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.address, int(self.port)))
            for metric in results.keys():
                sock.sendall("%s.%s\t%s\t%d\n" % \
                    (self.prefix, metric, results[metric], time.time()))
            sock.close()
            self.log.debug("Sent metrics to graphite server")
        except Exception, exc:
            self.log.exception("Failed to send metrics to graphite: %s", exc)
