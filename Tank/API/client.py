class TankAPIClient:
    def __init__(self, address, port, timeout):
        self.timeout = timeout
        self.port = port
        self.address = address