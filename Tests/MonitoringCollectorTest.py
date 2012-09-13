from Tests.TankTests import TankTestCase
import tempfile
import time
from MonCollector.collector import MonitoringCollector

class  MonitoringCollectorTestCase(TankTestCase):
    data = None
    
    def test_regular(self):
        mon = MonitoringCollector("config/mon1.conf", tempfile.mkstemp()[1])
        mon.prepare()
        mon.start()
        mon.poll()
        time.sleep(1)
        mon.poll()
        time.sleep(1)
        mon.poll()
        mon.stop()
