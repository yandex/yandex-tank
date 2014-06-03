import unittest
import logging

from Tank.Plugins.Phantom import PhantomConfig, PhantomPlugin
from Tests.TankTests import TankTestCase
from Tank.Plugins.PhantomUtils import StepperWrapper, AddressWizard


class PhantomConfigTestCase(TankTestCase):
    def setUp(self):
        pass

    def test_simple(self):
        core = self.get_core()
        core.load_configs(['config/phantom.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()

        foo = PhantomConfig(core)
        foo.read_config()
        foo.compose_config()

    def test_double(self):
        core = self.get_core()
        core.load_configs(['config/phantom_double.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()

        foo = PhantomConfig(core)
        foo.read_config()
        config = foo.compose_config()
        info = foo.get_info()
        logging.info(info.steps)
        self.assertEquals(len(info.steps), 450)

        conf_str = open(config).read()
        logging.info(conf_str)
        self.assertEquals(conf_str.count("io_benchmark_t"), 3)
        self.assertEquals(conf_str.count("benchmark_io "), 2)
        self.assertEquals(conf_str.count("benchmark_io1 "), 2)
        self.assertEquals(conf_str.count("benchmark_io2 "), 2)

        conf_str = open(config).read()
        logging.info(conf_str)
        self.assertEquals(conf_str.count("io_benchmark_t"), 3)

    def test_multiload_parsing(self):
        core = self.get_core()
        foo = StepperWrapper(core, PhantomPlugin.SECTION)
        foo.core.set_option('phantom', 'rps_schedule', 'const(1,1) line(1,100,60)\nstep(1,10,1,10)')
        foo.read_config()
        self.assertEquals(['const(1,1)', 'line(1,100,60)', 'step(1,10,1,10)'], foo.rps_schedule)


class AddressWizardTestCase(TankTestCase):
    def lookup_fn(self, host, port, family=None, socktype=None, proto=None, flags=None):
        """
        Mocking real resolver for unit testing purpose
        """
        results = {
            "ipv4host": "192.168.0.1",
            "ipv6host": "2001:db8::1"
        }

    def setUp(self):
        self.foo = AddressWizard()
        self.foo.lookup_fn = self.lookup_fn

    def test_v4_noport_resolve(self):
        res = self.foo.resolve("ipv4host")
        self.assertEquals((False, "127.0.0.1", None), res)

    def test_v6_noport_resolve(self):
        res = self.foo.resolve("ipv6host")
        self.assertEquals((True, "2001:db8::1", None), res)

    def test_v4_port_resolve(self):
        res = self.foo.resolve("ipv4host:443")
        self.assertEquals((False, "127.0.0.1", 443), res)

    def test_v6_port_resolve(self):
        res = self.foo.resolve("ipv6host:443")
        self.assertEquals((True, "2001:db8::1", 443), res)

    def test_v4_noport_noresolve(self):
        res = self.foo.resolve("127.0.0.1")
        self.assertEquals((False, "127.0.0.1", None), res)

    def test_v6_noport_noresolve(self):
        res = self.foo.resolve("2001:db8::1")
        self.assertEquals((True, "2001:db8::1", None), res)

    def test_v4_port_noresolve(self):
        res = self.foo.resolve("127.0.0.1:443")
        self.assertEquals((False, "127.0.0.1", 443), res)

    def test_v6_port_noresolve(self):
        res = self.foo.resolve("[2001:db8::1]:443")
        self.assertEquals((True, "2001:db8::1", 443), res)

    def test_v4_port_noresolve_braces(self):
        res = self.foo.resolve("[127.0.0.1]:443")
        self.assertEquals((False, "127.0.0.1", 443), res)

    def test_v6_port_resolve_braces(self):
        res = self.foo.resolve("[ipv6host]:443")
        self.assertEquals((True, "2001:db8::1", 443), res)

    def test_v4_noport_noresolve_braces(self):
        res = self.foo.resolve("[127.0.0.1]")
        self.assertEquals((False, "127.0.0.1", None), res)

    def test_v6_noport_resolve_braces(self):
        res = self.foo.resolve("[ipv6host]")
        self.assertEquals((True, "2001:db8::1", None), res)


if __name__ == '__main__':
    unittest.main()
