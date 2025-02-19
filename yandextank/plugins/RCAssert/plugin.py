''' Tank exit code check plugin '''

from yandextank.common.interfaces import AbstractPlugin


class Plugin(AbstractPlugin):
    SECTION = 'rcassert'

    def __init__(self, core, cfg, name):
        AbstractPlugin.__init__(self, core, cfg, name)
        self.ok_codes = []
        self.fail_code = 10

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["pass", "fail_code"]

    def configure(self):
        codes = self.get_option("pass", '').split(' ')
        for code in codes:
            if code:
                self.ok_codes.append(int(code))
        if bool(self.ok_codes) and (0 not in self.ok_codes):
            self.log.warning('RCAssert pass is missing zero exit code (0).')
        self.fail_code = int(self.get_option("fail_code", self.fail_code))

    def post_process(self, retcode):
        if not self.ok_codes:
            return retcode

        for code in self.ok_codes:
            self.log.debug("Comparing %s with %s codes", code, retcode)
            if code == int(retcode):
                self.log.info("Exit code %s was changed to 0 by RCAssert plugin", code)
                return 0

        self.log.info("Changing exit code to %s because RCAssert pass list was unsatisfied", self.fail_code)
        if self.fail_code > 0:
            self.errors.append(
                f'Changed exit code from {retcode} to {self.fail_code} because RCAssert pass list was unsatisfied'
            )
        return self.fail_code
