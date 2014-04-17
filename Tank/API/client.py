import json
import logging
import os
import urllib
import urllib2
import urlparse

from Tank.API.utils import MultiPartForm


class TankAPIClient:
    TICKET = "ticket"
    CONFIG = "config"
    FILENAME = "filename"
    EXCLUSIVE = "exclusive"
    DEFAULT_PORT = 8080

    # urls
    TANK_STATUS_JSON = "/tank_status.json"
    INTERRUPT_TEST_JSON = "/interrupt_test.json"
    START_TEST_JSON = "/start_test.json"
    PREPARE_TEST_JSON = "/prepare_test.json"
    TEST_STATUS_JSON = "/test_status.json"
    INITIATE_TEST_JSON = "/initiate_test.json"
    DOWNLOAD_ARTIFACT_URL = "/download_artifact"
    TEST_DATA_STREAM_JSON = "/aggregate_results_stream"

    # ticket statuses
    STATUS_BOOKED = "BOOKED"
    STATUS_PREPARING = "PREPARING"
    STATUS_PREPARED = "PREPARED"
    STATUS_RUNNING = "RUNNING"
    STATUS_FINISHING = "FINISHING"
    STATUS_FINISHED = "FINISHED"

    def __init__(self, address="http://localhost", timeout=5, ticket=None):
        self.timeout = timeout
        self.address = address
        if self.address[-1] == '/':
            self.address = self.address[:-1]

        if ticket:
            self.ticket = ticket
        else:
            self.ticket = None

        self.results_stream_offset = 0
        self.results_stream = None

    def __repr__(self):
        return "{%s %s}" % (self.__class__.__name__, self.address)

    def __build_url(self, url, params=None):
        parsed = urlparse.urlparse(self.address)

        if not ':' in parsed.netloc:
            url = "%s:%s%s" % (self.address, self.DEFAULT_PORT, url)
        else:
            url = self.address + url

        if not self.address.lower().startswith("http://") and not self.address.lower().startswith("https://"):
            url = "http://" + url

        if params:
            url += "?" + urllib.urlencode(params)

        return url

    def query_get(self, url, params=None):
        request = urllib2.Request(self.__build_url(url, params))
        logging.debug("API Request: %s", request.get_full_url())
        response = urllib2.urlopen(request, timeout=self.timeout)
        if response.getcode() != 200:
            resp = response.read()
            logging.debug("Full response: %s", resp)
            msg = "Tank API request failed, response code %s"
            raise RuntimeError(msg % response.getcode())
        resp = response.read()
        logging.debug("Response: %s", resp)
        return json.loads(resp)

    def query_post(self, url, params, content_type, body):
        request = urllib2.Request(self.__build_url(url, params))
        request.add_header('Content-Type', content_type)
        request.add_header('Content-Length', len(body))
        request.add_data(body)
        logging.debug("API Request: %s", request.get_full_url())

        response = urllib2.urlopen(request, timeout=self.timeout)
        if response.getcode() != 200:
            resp = response.read()
            logging.debug("Full response: %s", resp)
            msg = "Tank API request failed, response code %s"
            raise RuntimeError(msg % response.getcode())
        resp = response.read()
        logging.debug("Response: %s", resp)
        return json.loads(resp)

    def query_get_to_file(self, url, params, local_name):
        request = urllib2.Request(self.__build_url(url, params))
        logging.debug("API Request: %s", request.get_full_url())
        response = urllib2.urlopen(request, timeout=self.timeout)
        if response.getcode() != 200:
            resp = response.read()
            logging.debug("Full response: %s", resp)
            msg = "Tank API request failed, response code %s"
            raise RuntimeError(msg % response.getcode())

        with open(local_name, "wb") as fd:
            fd.write(response.read())

    def query_get_stream(self, url, params):
        request = urllib2.Request(self.__build_url(url, params))
        logging.debug("API Request: %s", request.get_full_url())
        response = urllib2.urlopen(request, timeout=self.timeout)

        if response.getcode() != 200:
            resp = response.read()
            logging.debug("Full response: %s", resp)
            msg = "Tank API request failed, response code %s"
            raise RuntimeError(msg % response.getcode())

        return response

    def get_tank_status(self):
        return self.query_get(self.TANK_STATUS_JSON)

    def initiate_test(self, exclusive):
        """        get ticket        """
        response = self.query_get(self.INITIATE_TEST_JSON, {self.EXCLUSIVE: exclusive})
        self.ticket = response[self.TICKET]
        return self.ticket

    def get_test_status(self):
        return self.query_get(self.TEST_STATUS_JSON, {self.TICKET: self.ticket})

    def prepare_test(self, config_file, additional_files=()):
        """ send files, but do not wait for preparing """
        body = MultiPartForm()

        with open(config_file) as fd:
            body.add_file_as_string(self.CONFIG, os.path.basename(config_file), fd.read())

        for extra_file in additional_files:
            with open(extra_file) as fd:
                body.add_file_as_string("file_%s" % extra_file, os.path.basename(extra_file), fd.read())

        self.query_post(self.PREPARE_TEST_JSON, {self.TICKET: self.ticket}, body.get_content_type(), str(body))

    def start_test(self):
        self.query_get(self.START_TEST_JSON, {self.TICKET: self.ticket})

    def interrupt(self):
        self.query_get(self.INTERRUPT_TEST_JSON, {self.TICKET: self.ticket})

    def download_artifact(self, remote_name, local_name):
        self.query_get_to_file(self.DOWNLOAD_ARTIFACT_URL, {self.TICKET: self.ticket, self.FILENAME: remote_name},
                               local_name)

    def get_results_stream(self):
        if not self.results_stream:
            # TODO: handle reconnect
            self.results_stream = self.query_get_stream(self.TEST_DATA_STREAM_JSON,
                                                        {self.TICKET: self.ticket,
                                                         "offset": self.results_stream_offset})
        return self.results_stream
