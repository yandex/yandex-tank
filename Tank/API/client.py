class TankAPIClient:
    READY = 0
    BOOKED = 1
    PREPARING = 2
    PREPARED = 3
    TESTING = 4
    FINISHED = 5


    def __init__(self, address, port, timeout):
        self.ticket = None
        self.timeout = timeout
        self.port = port
        self.address = address

    def __repr__(self):
        return "{%s %s:%s}" % (self.__class__.__name__, self.address, self.port)

    def book(self, exclusive):
        """        get ticket        """
        self.ticket = "test"
        return True

    def release(self):
        """ release ticket        """
        self.__init__(self.address, self.port, self.timeout)

    def prepare_test(self, config_file, additional_files):
        """ send files, but do not wait for preparing """

    def get_status(self):
        return None

    def start_test(self):
        pass

    def interrupt(self):
        pass

    def get_artifacts_list(self):
        return ["tank.log"]

    def download_artifact(self, remote_name, local_name):
        pass