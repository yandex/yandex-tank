from yandextank.plugins.ShellExec import ShellExecPlugin
from TankTests import TankTestCase
import logging
import select
import subprocess
import unittest


class ShellExecPluginTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        core.load_configs(['config/shellexec.conf'])
        self.foo = ShellExecPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None

    def test_run(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        self.foo.end_test(0)

    def test_select(self):
        pipes = subprocess.Popen(["pwd"], stdout=subprocess.PIPE)
        r, w, x = select.select([pipes.stdout], [], [], 1)
        logging.info("selected: %s %s %s", r, w, x)

if __name__ == '__main__':
    unittest.main()
