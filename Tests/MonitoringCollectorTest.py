from Monitoring.collector import MonitoringCollector
from Tests.TankTests import TankTestCase
import tempfile
import time

class  MonitoringCollectorTestCase(TankTestCase):
    data = None
    
    def test_regular(self):
        mon = MonitoringCollector("config/mon1.conf", tempfile.mkdtemp()[1])
        mon.prepare()
        mon.start()
        mon.poll()
        time.sleep(1)
        mon.poll()
        time.sleep(1)
        mon.poll()
        mon.stop()
