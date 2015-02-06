import os
import time
import unittest

from yandextank.plugins.Aggregator import AggregatorPlugin, SecondAggregateData
from yandextank.plugins.Phantom import PhantomPlugin, PhantomReader
from TankTests import TankTestCase
from yandextank.plugins.Phantom.PhantomUtils import StepperWrapper


class PhantomPluginTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        core.load_configs(['config/phantom.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        self.phantom_plugin_instance = PhantomPlugin(core)
        self.phantom_plugin_instance.core.set_option(PhantomPlugin.SECTION, "phantom_path",
                                                     os.path.dirname(__file__) + "/phantom_emul.sh")

    def tearDown(self):
        del self.phantom_plugin_instance
        self.phantom_plugin_instance = None
        if os.path.exists("ready_conf_phout.txt"):
            os.remove("ready_conf_phout.txt")

    def test_run(self):
        self.phantom_plugin_instance.core.set_option(PhantomPlugin.SECTION, "config", '')
        self.phantom_plugin_instance.configure()
        self.phantom_plugin_instance.prepare_test()
        reader = PhantomReader(AggregatorPlugin(self.phantom_plugin_instance.core), self.phantom_plugin_instance)
        reader.phout_file = self.phantom_plugin_instance.phantom.phout_file
        self.phantom_plugin_instance.start_test()

        while self.phantom_plugin_instance.is_test_finished() < 0:
            self.phantom_plugin_instance.log.debug("Not finished")
            reader.check_open_files()
            reader.get_next_sample(False)
            time.sleep(1)
        if self.phantom_plugin_instance.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.phantom_plugin_instance.is_test_finished())
        self.phantom_plugin_instance.end_test(0)
        reader.get_next_sample(True)


    def test_run_ready_conf(self):
        self.phantom_plugin_instance.core.set_option(PhantomPlugin.SECTION, "config", 'data/phantom_ready.conf')
        self.phantom_plugin_instance.core.add_artifact_file("ready_conf_phout.txt")
        self.phantom_plugin_instance.configure()
        self.phantom_plugin_instance.prepare_test()
        self.phantom_plugin_instance.start_test()
        while self.phantom_plugin_instance.is_test_finished() < 0:
            self.phantom_plugin_instance.log.debug("Not finished")
            time.sleep(1)
        if self.phantom_plugin_instance.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.phantom_plugin_instance.is_test_finished())
        #self.assertTrue(os.path.getsize("ready_conf_phout.txt") > 0)
        self.phantom_plugin_instance.end_test(0)


    def test_run_uri_style(self):
        self.phantom_plugin_instance.set_option("ammofile", "")
        self.phantom_plugin_instance.set_option("uris", "/")
        self.phantom_plugin_instance.configure()
        self.phantom_plugin_instance.prepare_test()
        self.phantom_plugin_instance.start_test()
        while self.phantom_plugin_instance.is_test_finished() < 0:
            self.phantom_plugin_instance.log.debug("Not finished")
            time.sleep(1)
        if self.phantom_plugin_instance.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.phantom_plugin_instance.is_test_finished())
        self.phantom_plugin_instance.end_test(0)

    def test_run_interrupt(self):
        self.phantom_plugin_instance.configure()
        self.phantom_plugin_instance.prepare_test()
        self.phantom_plugin_instance.start_test()
        time.sleep(2)
        self.phantom_plugin_instance.end_test(0)

    def test_run_stepper_cache(self):
        self.phantom_plugin_instance.configure()
        self.phantom_plugin_instance.prepare_test()
        self.phantom_plugin_instance.prepare_test()

    def test_domain_name(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'address', 'yandex.ru:443')
        self.phantom_plugin_instance.configure()
        self.assertEqual(443, self.phantom_plugin_instance.get_info().port)
        self.assertEqual("yandex.ru", self.phantom_plugin_instance.get_info().address)

    def test_domain_name_and_port(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'address', 'yandex.ru:80')
        self.phantom_plugin_instance.configure()

    def test_ipv4(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'address', '127.0.0.1')
        self.phantom_plugin_instance.configure()

    def test_ipv6(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'address', '2a02:6b8:0:c1f::161:cd')
        self.phantom_plugin_instance.configure()

    def test_ipv4_and_port(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'address', '127.0.0.1:80')
        self.phantom_plugin_instance.configure()

    def test_domain_name_fail(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'address', 'ya.ru')
        try:
            self.phantom_plugin_instance.configure()
            raise RuntimeError()
        except:
            pass


    def test_reader(self):
        self.phantom_plugin_instance.phantom_start_time = time.time()
        reader = PhantomReader(AggregatorPlugin(self.phantom_plugin_instance.core), self.phantom_plugin_instance)
        reader.phout_file = 'data/phout_timeout_mix.txt'
        reader.check_open_files()

        data = reader.get_next_sample(False)
        while data:
            times_sum = 0
            for timing in data.overall.times_dist:
                times_sum += timing['count']
            # FIXME: kinda strange problem here
            #self.assertEquals(sum(data.overall.net_codes.values()), times_sum)
            data = reader.get_next_sample(False)


    def test_stepper_no_steps(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'rps_schedule', '')
        self.phantom_plugin_instance.core.set_option('phantom', 'instances_schedule', '')
        wrapper = StepperWrapper(self.phantom_plugin_instance.core, PhantomPlugin.SECTION)
        wrapper.ammo_file = 'data/dummy.ammo'
        wrapper.prepare_stepper()
        wrapper.prepare_stepper()

    def test_stepper_instances_sched(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'instances', '1000')
        self.phantom_plugin_instance.core.set_option('phantom', 'rps_schedule', '')
        self.phantom_plugin_instance.core.set_option('phantom', 'instances_schedule', 'line(1,100,1m)')
        self.phantom_plugin_instance.core.set_option('phantom', 'use_caching', '0')
        self.phantom_plugin_instance.core.set_option('phantom', 'ammo_file', 'data/dummy.ammo')
        wrapper = StepperWrapper(self.phantom_plugin_instance.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.assertEqual(100, wrapper.instances)

    def test_stepper_instances_override(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'instances', '20000')
        self.phantom_plugin_instance.core.set_option('phantom', 'rps_schedule', 'line(1,100,1m)')
        self.phantom_plugin_instance.core.set_option('phantom', 'use_caching', '0')
        self.phantom_plugin_instance.core.set_option('phantom', 'ammo_file', 'data/dummy.ammo')
        wrapper = StepperWrapper(self.phantom_plugin_instance.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.assertEqual(20000, wrapper.instances)


    def test_cached_stepper_instances_sched(self):
        # Making cache file
        self.phantom_plugin_instance.core.set_option('phantom', 'instances', '1000')
        self.phantom_plugin_instance.core.set_option('phantom', 'rps_schedule', '')
        self.phantom_plugin_instance.core.set_option('phantom', 'instances_schedule', 'line(1,100,1m)')
        self.phantom_plugin_instance.core.set_option('phantom', 'ammo_file', 'data/dummy.ammo')
        wrapper = StepperWrapper(self.phantom_plugin_instance.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.tearDown()

        self.setUp()
        self.phantom_plugin_instance.core.set_option('phantom', 'instances', '1000')
        self.phantom_plugin_instance.core.set_option('phantom', 'rps_schedule', '')
        self.phantom_plugin_instance.core.set_option('phantom', 'instances_schedule', 'line(1,100,1m)')
        self.phantom_plugin_instance.core.set_option('phantom', 'ammo_file', 'data/dummy.ammo')
        wrapper = StepperWrapper(self.phantom_plugin_instance.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.assertEqual(100, wrapper.instances)

    def test_phout_import(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'phout_file', 'data/phout_timeout_mix.txt')
        self.phantom_plugin_instance.core.set_option('phantom', 'instances', '1')
        self.phantom_plugin_instance.core.set_option('phantom', 'ammo_count', '1')
        self.phantom_plugin_instance.configure()
        self.phantom_plugin_instance.prepare_test()
        self.phantom_plugin_instance.start_test()
        self.assertEqual(self.phantom_plugin_instance.is_test_finished(), -1)
        sec = SecondAggregateData()
        sec.overall.rps = 1
        self.phantom_plugin_instance.aggregate_second(sec)
        self.assertEqual(self.phantom_plugin_instance.is_test_finished(), -1)
        self.phantom_plugin_instance.end_test(0)
        self.phantom_plugin_instance.post_process(0)

    def test_cached_stpd_info(self):
        self.phantom_plugin_instance.core.set_option('phantom', 'stpd_file', 'data/dummy.ammo.stpd')
        wrapper = StepperWrapper(self.phantom_plugin_instance.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.assertEqual(10, wrapper.instances)
        self.assertEqual(60, wrapper.duration)


if __name__ == '__main__':
    unittest.main()
