'''
Contains shellexec plugin
'''
from ...common import util
from ...common.interfaces import AbstractPlugin


class Plugin(AbstractPlugin):
    '''
    ShellExec plugin
    allows executing shell scripts before/after test
    '''
    SECTION = 'shellexec'

    def __init__(self, core):
        AbstractPlugin.__init__(self, core)
        self.catch_out = False
        self.end = None
        self.poll = None
        self.prepare = None
        self.start = None
        self.postprocess = None

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return ["prepare", "start", "end", "poll", "post_process", "catch_out"]

    def configure(self):
        self.catch_out = True if self.get_option("catch_out", False) else False
        self.prepare = self.get_option("prepare", '')
        self.start = self.get_option("start", '')
        self.end = self.get_option("end", '')
        self.poll = self.get_option("poll", '')
        self.postprocess = self.get_option("post_process", '')

    def prepare_test(self):
        if self.prepare:
            self.execute(self.prepare)

    def start_test(self):
        if self.start:
            self.execute(self.start)

    def is_test_finished(self):
        if self.poll:
            self.log.info("Executing: %s", self.poll)
            retcode = util.execute(
                self.poll,
                shell=True,
                poll_period=0.1,
                catch_out=self.catch_out)[0]
            if retcode:
                self.log.warn(
                    "Non-zero exit code, interrupting test: %s", retcode)
                return retcode
        return -1

    def end_test(self, retcode):
        if self.end:
            self.execute(self.end)
        return retcode

    def post_process(self, retcode):
        if self.postprocess:
            self.execute(self.postprocess)
        return retcode

    def execute(self, cmd):
        '''
        Execute and check exit code
        '''
        self.log.info("Executing: %s", cmd)
        retcode = util.execute(
            cmd, shell=True, poll_period=0.1, catch_out=self.catch_out)[0]
        if retcode:
            raise RuntimeError("Subprocess returned %s" % retcode)
