import logging
log = logging.getLogger(__name__)


class LoadTest(object):
    def __init__(self, gun):
        self.gun = gun

    def case1(self, missile):
        with self.gun.measure("case1"):
            log.info("Shoot case 1: %s", missile)

    def case2(self, missile):
        with self.gun.measure("case2"):
            log.info("Shoot case 2: %s", missile)

    def setup(self):
        log.info("Setting up LoadTest")

    def teardown(self):
        log.info("Tearing down LoadTest")
