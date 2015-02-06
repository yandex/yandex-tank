import socket
import unittest
import logging

from yandextank.plugins.Phantom import PhantomConfig, PhantomPlugin
from TankTests import TankTestCase
from yandextank.plugins.Phantom.PhantomUtils import \
    StepperWrapper, AddressWizard


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
    results = {
        "127.0.0.1": ("127.0.0.1", socket.AF_INET),
        "ipv4host": ("192.168.0.1", socket.AF_INET),
        "::": ("::", socket.AF_INET6),
        "2001:db8::1": ("2001:db8::1", socket.AF_INET6),
        "ipv6host": ("2001:db8::1", socket.AF_INET6),
        "exc1": socket.gaierror("Simulated error")
    }

    def lookup_fn(self, host, port, family=None, socktype=None, proto=None, flags=None):
        """
        Mocking real resolver for unit testing purpose
        """
        if host not in self.results:
            raise socket.gaierror("Host not found: %s" % host)

        logging.debug("Mocking resolve %s=>%s", host, self.results[host])

        if isinstance(self.results[host], IOError):
            raise self.results[host]

        return [(self.results[host][1], None, None, None, (self.results[host][0], port))]

    def setUp(self):
        self.foo = AddressWizard()
        self.foo.lookup_fn = self.lookup_fn

    def test_v4_noport_resolve(self):
        res = self.foo.resolve("ipv4host")
        self.assertEquals((False, "192.168.0.1", 80, "ipv4host"), res)

    def test_v6_noport_resolve(self):
        res = self.foo.resolve("ipv6host")
        self.assertEquals((True, "2001:db8::1", 80, "ipv6host"), res)

    def test_v4_port_resolve(self):
        res = self.foo.resolve("ipv4host:443")
        self.assertEquals((False, "192.168.0.1", 443, "ipv4host"), res)

    def test_v6_port_resolve(self):
        res = self.foo.resolve("ipv6host:443")
        self.assertEquals((True, "2001:db8::1", 443, "ipv6host"), res)

    def test_v4_noport_noresolve(self):
        res = self.foo.resolve("127.0.0.1")
        self.assertEquals((False, "127.0.0.1", 80, "127.0.0.1"), res)

    def test_v6_noport_noresolve(self):
        res = self.foo.resolve("2001:db8::1")
        self.assertEquals((True, "2001:db8::1", 80, "2001:db8::1"), res)

    def test_v4_port_noresolve(self):
        res = self.foo.resolve("127.0.0.1:443")
        self.assertEquals((False, "127.0.0.1", 443, "127.0.0.1"), res)

    def test_v6_port_noresolve_braces(self):
        res = self.foo.resolve("[2001:db8::1]:443")
        self.assertEquals((True, "2001:db8::1", 443, "2001:db8::1"), res)

    def test_v4_port_noresolve_braces(self):
        res = self.foo.resolve("[127.0.0.1]:443")
        self.assertEquals((False, "127.0.0.1", 443, "127.0.0.1"), res)

    def test_v6_port_resolve_braces(self):
        res = self.foo.resolve("[ipv6host]:443")
        self.assertEquals((True, "2001:db8::1", 443, "ipv6host"), res)

    def test_v4_port_resolve_braces(self):
        res = self.foo.resolve("[ipv4host]:443")
        self.assertEquals((False, "192.168.0.1", 443, "ipv4host"), res)

    def test_v4_noport_resolve_braces(self):
        res = self.foo.resolve("[ipv4host]")
        self.assertEquals((False, "192.168.0.1", 80, "ipv4host"), res)

    def test_v4_noport_noresolve_braces(self):
        res = self.foo.resolve("[127.0.0.1]")
        self.assertEquals((False, "127.0.0.1", 80, "127.0.0.1"), res)

    def test_v6_noport_resolve_braces(self):
        res = self.foo.resolve("[ipv6host]")
        self.assertEquals((True, "2001:db8::1", 80, "ipv6host"), res)

    def test_v6_noport_noresolve_braces(self):
        res = self.foo.resolve("[2001:db8::1]")
        self.assertEquals((True, "2001:db8::1", 80, "2001:db8::1"), res)

    def test_error1(self):
        try:
            res = self.foo.resolve("ipv4host:20:30")
            self.fail()
        except:
            pass

    def test_error2(self):
        try:
            res = self.foo.resolve("exc1:30")
            self.fail()
        except:
            pass


if __name__ == '__main__':
    unittest.main()
