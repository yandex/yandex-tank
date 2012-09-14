from Tests.TankTests import TankTestCase
import tempfile
import time
from MonCollector.collector import MonitoringCollector, MonitoringDataListener
from Tank.Plugins.Monitoring import MonitoringPlugin
from Tank.Core import TankCore
import logging

class  MonitoringCollectorTestCase(TankTestCase):
    data = None
    
    def test_collector(self):
        mon = MonitoringCollector("config/mon1.conf", tempfile.mkstemp()[1])
        listener = TestMonListener()
        mon.add_listener(listener)
        mon.prepare()
        mon.start()
        mon.poll()
        self.assertEquals([], listener.data)
        listener.data=[]
        time.sleep(1)
        mon.poll()
        self.assertNotEquals([], listener.data)
        self.assertTrue(listener.data[0].startswith('start;'))
        listener.data=[]
        time.sleep(2)
        mon.poll()
        self.assertNotEquals([], listener.data)
        self.assertFalse(listener.data[0].startswith('start;'))
        listener.data=[]
        time.sleep(3)
        mon.poll()
        self.assertNotEquals([], listener.data)
        self.assertFalse(listener.data[0].startswith('start;'))
        listener.data=[]
        mon.stop()

    # TODO: add unit tests: disabled, default, and set config            
    def test_plugin_disabled(self):
        core = TankCore()
        mon = MonitoringPlugin(core)
        core.set_option(mon.SECTION, 'config', 'none')
        mon.configure()
        mon.prepare_test()
        mon.start_test()
        self.assertEquals(-1, mon.is_test_finished())
        self.assertEquals(None, mon.monitoring)
        time.sleep(1)
        self.assertEquals(-1, mon.is_test_finished())
        mon.end_test(0)
        mon.post_process(0)


class TestMonListener(MonitoringDataListener):
    def __init__(self):
        self.data = []
    
    def monitoring_data(self, data_string):
        logging.debug("MON DATA: %s", data_string)
        self.data.append(data_string)
