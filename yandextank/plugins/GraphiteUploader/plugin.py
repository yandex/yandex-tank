'''Graphite Uploader plugin that sends aggregated data to Graphite server'''

from pkg_resources import resource_string
from yandextank.plugins.Aggregator import \
    AggregateResultListener, AggregatorPlugin
from yandextank.core import AbstractPlugin
import logging
import socket
import string
import time
import datetime


class GraphiteUploaderPlugin(AbstractPlugin, AggregateResultListener):

    '''Graphite data uploader'''

    SECTION = 'graphite'

    @staticmethod
    def get_key():
        return __file__

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.graphite_client = None

    def get_available_options(self):
        return ["address", "port", "prefix", "web_port"]

    def start_test(self):
        start_time = datetime.datetime.now()
        self.start_time = start_time.strftime("%H:%M%%20%Y%m%d")

    def end_test(self, retcode):
        end_time = datetime.datetime.now() + datetime.timedelta(minutes=1)
        self.end_time = end_time.strftime("%H:%M%%20%Y%m%d")
        return retcode

    def configure(self):
        '''Read configuration'''
        self.address = self.get_option("address", "")
        if self.address == "":
            self.log.warning(
                "Graphite uploader is not configured and will not send any data")
        else:
            port = self.get_option("port", "2003")
            self.web_port = self.get_option("web_port", "8080")
            self.prefix = self.get_option("prefix", "one_sec.yandex_tank")
            specified_template = self.get_option("template", "")
            if specified_template != "":
                self.template = open(specified_template, 'r').read()
            else:
                default_template = "graphite.tpl"
                if self.get_option("js", "1") == "1":
                    default_template = "graphite-js.tpl"
                self.template = resource_string(__name__, 'config/' + default_template)
            self.graphite_client = GraphiteClient(
                self.prefix, self.address, port)
            aggregator = self.core.get_plugin_of_type(AggregatorPlugin)
            aggregator.add_result_listener(self)

    def aggregate_second(self, data):
        """
        @data: SecondAggregateData
        """
        # TODO: Use ts from data
        if self.graphite_client:
            results = {}
            overall = GraphiteUploaderPlugin.__flatten(
                data.overall.__dict__, "overall")
            cumulative = GraphiteUploaderPlugin.__flatten(
                data.cumulative.__dict__, "cumulative")
            results.update(overall)
            results.update(cumulative)
            for marker in data.cases.keys():
                results.update(GraphiteUploaderPlugin.__flatten(
                    data.cases[marker].__dict__, 'markers.%s' % marker)
                )
            self.graphite_client.submit(results)

    def post_process(self, retcode):
        if self.graphite_client:
            graphite_html = self.core.mkstemp(".html", "graphite_")
            self.core.add_artifact_file(graphite_html)
            with open(graphite_html, 'w') as graphite_html_file:
                graphite_html_file.write(
                    string.Template(self.template).safe_substitute(
                        host=self.address,
                        width=1000,
                        height=400,
                        start_time=self.start_time,
                        end_time=self.end_time,
                        prefix=self.prefix,
                        web_port=self.web_port,
                    )
                )
        return retcode

    @staticmethod
    def __flatten(dic, prefix):
        '''
        recursively pass through a dict and flatten it\'s "internal" dicts
        '''
        results = {}
        if dic is not None:
            try:
                for key in dic.keys():
                    if type(dic[key]) in [float, int]:
                        results["%s.%s" % (
                            prefix,
                            str(key).translate(string.maketrans(".", "_"))
                        )] = dic[key]
                    elif type(dic[key] in [dict]):
                        results.update(
                            GraphiteUploaderPlugin.__flatten(
                                dic[key],
                                "%s.%s" % (
                                    prefix,
                                    key.translate(string.maketrans(".", "_"))
                                )
                            )
                        )
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
        self.log.debug(
            "Created a Graphite listener with address = '%s', port = '%s', prefix = '%s'" %
            (address, port, prefix)
        )

    def submit(self, results):
        '''publish results to Graphite'''
        self.log.debug("Trying to send metrics to server...")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.address, int(self.port)))
            for metric in results.keys():
                sock.sendall(
                    "%s.%s\t%s\t%d\n" %
                    (self.prefix, metric, results[metric], time.time())
                )
            sock.close()
            self.log.debug("Sent metrics to graphite server")
        except Exception, exc:
            self.log.exception("Failed to send metrics to graphite: %s", exc)
