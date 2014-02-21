import os
import time
import unittest

from Tank.Plugins.Aggregator import AggregatorPlugin, SecondAggregateData
from Tank.Plugins.Phantom import PhantomPlugin, PhantomReader
from Tests.TankTests import TankTestCase
from Tank.Plugins.PhantomUtils import StepperWrapper


class PhantomPluginTestCase(TankTestCase):
    def setUp(self):
        core = self.get_core()
        core.load_configs(['config/phantom.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        self.foo = PhantomPlugin(core)

    def tearDown(self):
        del self.foo
        self.foo = None
        if os.path.exists("ready_conf_phout.txt"):
            os.remove("ready_conf_phout.txt")

    def test_run(self):
        self.foo.core.set_option(PhantomPlugin.SECTION, "config", '')
        self.foo.configure()
        self.foo.prepare_test()
        reader = PhantomReader(AggregatorPlugin(self.foo.core), self.foo)
        reader.phout_file = self.foo.phantom.phout_file
        self.foo.start_test()

        while self.foo.is_test_finished() < 0:
            self.foo.log.debug("Not finished")
            reader.check_open_files()
            reader.get_next_sample(False)
            time.sleep(1)
        if self.foo.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.foo.is_test_finished())
        self.foo.end_test(0)
        reader.get_next_sample(True)


    def test_run_ready_conf(self):
        self.foo.core.set_option(PhantomPlugin.SECTION, "config", 'data/phantom_ready.conf')
        self.foo.core.add_artifact_file("ready_conf_phout.txt")
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        while self.foo.is_test_finished() < 0:
            self.foo.log.debug("Not finished")
            time.sleep(1)
        if self.foo.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.foo.is_test_finished())
        self.assertTrue(os.path.getsize("ready_conf_phout.txt") > 0)
        self.foo.end_test(0)


    def test_run_uri_style(self):
        self.foo.set_option("ammofile", "")
        self.foo.set_option("uris", "/")
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        while self.foo.is_test_finished() < 0:
            self.foo.log.debug("Not finished")
            time.sleep(1)
        if self.foo.is_test_finished() != 0:
            raise RuntimeError("RC: %s" % self.foo.is_test_finished())
        self.foo.end_test(0)

    def test_run_interrupt(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        time.sleep(2)
        self.foo.end_test(0)

    def test_run_stepper_cache(self):
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.prepare_test()

    def test_domain_name(self):
        self.foo.core.set_option('phantom', 'address', 'yandex.ru')
        self.foo.configure()


    def test_domain_name_fail(self):
        self.foo.core.set_option('phantom', 'address', 'ya.ru')
        try:
            self.foo.configure()
            raise RuntimeError()
        except:
            pass


    def test_reader(self):
        self.foo.phantom_start_time = time.time()
        reader = PhantomReader(AggregatorPlugin(self.foo.core), self.foo)
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
        self.foo.core.set_option('phantom', 'rps_schedule', '')
        self.foo.core.set_option('phantom', 'instances_schedule', '')
        wrapper = StepperWrapper(self.foo.core, PhantomPlugin.SECTION)
        wrapper.ammo_file = 'data/dummy.ammo'
        wrapper.prepare_stepper()
        wrapper.prepare_stepper()

    def test_stepper_instances_sched(self):
        self.foo.core.set_option('phantom', 'instances', '1000')
        self.foo.core.set_option('phantom', 'rps_schedule', '')
        self.foo.core.set_option('phantom', 'instances_schedule', 'line(1,100,1m)')
        self.foo.core.set_option('phantom', 'use_caching', '0')
        self.foo.core.set_option('phantom', 'ammo_file', 'data/dummy.ammo')
        wrapper = StepperWrapper(self.foo.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.assertEqual(100, wrapper.instances)

    def test_cached_stepper_instances_sched(self):
        
        # Making cache file
        self.foo.core.set_option('phantom', 'instances', '1000')
        self.foo.core.set_option('phantom', 'rps_schedule', '')
        self.foo.core.set_option('phantom', 'instances_schedule', 'line(1,100,1m)')
        self.foo.core.set_option('phantom', 'ammo_file', 'data/dummy.ammo')
        wrapper = StepperWrapper(self.foo.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.tearDown()
        
        self.setUp()
        self.foo.core.set_option('phantom', 'instances', '1000')
        self.foo.core.set_option('phantom', 'rps_schedule', '')
        self.foo.core.set_option('phantom', 'instances_schedule', 'line(1,100,1m)')
        self.foo.core.set_option('phantom', 'ammo_file', 'data/dummy.ammo')
        wrapper = StepperWrapper(self.foo.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.assertEqual(100, wrapper.instances)

    def test_phout_import(self):
        self.foo.core.set_option('phantom', 'phout_file', 'data/phout_timeout_mix.txt')
        self.foo.core.set_option('phantom', 'instances', '1')
        self.foo.core.set_option('phantom', 'ammo_count', '1')
        self.foo.configure()
        self.foo.prepare_test()
        self.foo.start_test()
        self.assertEqual(self.foo.is_test_finished(), -1)
        sec = SecondAggregateData()
        sec.overall.RPS = 1
        self.foo.aggregate_second(sec)
        self.assertEqual(self.foo.is_test_finished(), -1)
        self.assertEqual(self.foo.is_test_finished(), 0)
        self.foo.end_test(0)
        self.foo.post_process(0)

    def test_cached_stpd_info(self):
        self.foo.core.set_option('phantom', 'stpd_file', 'data/dummy.ammo.stpd')
        wrapper = StepperWrapper(self.foo.core, PhantomPlugin.SECTION)
        wrapper.read_config()
        wrapper.prepare_stepper()
        self.assertEqual(10, wrapper.instances)
        self.assertEqual(60, wrapper.duration)

if __name__ == '__main__':
    unittest.main()
