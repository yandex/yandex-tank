import json
import logging
import os
import urllib
import urllib2

from Tank.API.utils import MultiPartForm


class TankAPIClient:
    # ticket statuses
    UNKNOWN = "UNKNOWN"
    BOOKED = "BOOKED"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    RUNNING = "RUNNING"
    FINISHING = "FINISHING"
    FINISHED = "FINISHED"

    def __init__(self, address="http://localhost", timeout=5, ticket=None):
        self.timeout = timeout
        self.address = address
        if self.address[-1] == '/':
            self.address = self.address[:-1]

        if ticket:
            self.ticket = ticket
        else:
            self.ticket = None

    def __repr__(self):
        return "{%s %s}" % (self.__class__.__name__, self.address)

    def __build_url(self, url, params=None):
        url = self.address + url

        if not self.address.lower().startswith("http://") and not self.address.lower().startswith("https://"):
            url = "http://" + url

        if params:
            url += "?" + urllib.urlencode(params)

        return url

    def query_get(self, url, params=None):
        request = urllib2.Request(self.__build_url(url, params))
        logging.debug("API Request: %s", request.get_full_url())
        response = urllib2.urlopen(request)
        if response.getcode() != 200:
            resp = response.read()
            logging.debug("Full response: %s", resp)
            msg = "Tank API request failed, response code %s"
            raise RuntimeError(msg % response.getcode())
        return json.loads(response.read())

    def query_post(self, url, params, content_type, body):
        request = urllib2.Request(self.__build_url(url, params))
        request.add_header('Content-Type', content_type)
        request.add_header('Content-Length', len(body))
        request.add_data(body)

        response = urllib2.urlopen(request)
        if response.getcode() != 200:
            resp = response.read()
            logging.debug("Full response: %s", resp)
            msg = "Tank API request failed, response code %s"
            raise RuntimeError(msg % response.getcode())
        return json.loads(response.read())

    def query_get_to_file(self, url, params, local_name):
        request = urllib2.Request(self.__build_url(url, params))
        response = urllib2.urlopen(request)
        if response.getcode() != 200:
            resp = response.read()
            logging.debug("Full response: %s", resp)
            msg = "Tank API request failed, response code %s"
            raise RuntimeError(msg % response.getcode())

        with open(local_name, "wb") as fd:
            fd.write(response.read())

    def get_tank_status(self):
        return self.query_get("/tank_status.json")

    def initiate_test(self, exclusive):
        """        get ticket        """
        response = self.query_get("/initiate_test.json", {"exclusive": exclusive})
        self.ticket = response["ticket"]
        return self.ticket

    def get_test_status(self):
        return self.query_get("/test_status.json", {"ticket": self.ticket})

    def prepare_test(self, config_file, additional_files=()):
        """ send files, but do not wait for preparing """
        body = MultiPartForm()

        with open(config_file) as fd:
            body.add_file_as_string("config", "load.ini", fd.read())

        for extra_file in additional_files:
            with open(extra_file) as fd:
                body.add_file_as_string("file_%s" % extra_file, os.path.basename(extra_file), fd.read())

        self.query_post("/prepare_test.json", {"ticket": self.ticket}, body.get_content_type(), str(body))

    def start_test(self):
        self.query_get("/start_test.json", {"ticket": self.ticket})

    def interrupt(self):
        self.query_get("/interrupt_test.json", {"ticket": self.ticket})

    def download_artifact(self, remote_name, local_name):
        self.query_get_to_file("/download_artifact", {"ticket": self.ticket, "filename": remote_name}, local_name)

