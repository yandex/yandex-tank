import logging
import os

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

    def __init__(self, address, timeout, ticket=None):
        self.timeout = timeout
        self.address = address
        if ticket:
            self.ticket = ticket
        else:
            self.ticket = None

    def __repr__(self):
        return "{%s %s}" % (self.__class__.__name__, self.address)

    def query_get(self, url, params=None):
        return {}

    def query_post(self, url, params, body):
        return {}

    def query_get_to_file(self, url, params, local_name):
        return {}

    def get_tank_status(self):
        return self.query_get("/tank_status.json")

    def book(self, exclusive):
        """        get ticket        """
        if self.ticket:
            raise RuntimeError("Already booked a ticket: %s" % self.ticket)

        response = self.query_get("/book_test.json", {"exclusive": exclusive})
        self.ticket = response["ticket"]
        return self.ticket

    def release(self):
        """ release ticket        """
        if self.ticket:
            self.query_get("/release_tank.json")
        else:
            logging.debug("No ticket, nothing to release")

        # may I use this to clean up the state???
        self.__init__(self.address, self.timeout, None)

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

        self.query_post("/prepare_test.json", {"ticket": self.ticket}, str(body))

    def start_test(self):
        self.query_get("/start_test.json", {"ticket": self.ticket})

    def interrupt(self):
        self.query_get("/interrupt_test.json", {"ticket": self.ticket})

    def download_artifact(self, remote_name, local_name):
        self.query_get_to_file("/download_artifact", {"ticket": self.ticket, "filename": remote_name}, local_name)

