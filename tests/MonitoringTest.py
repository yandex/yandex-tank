from yandextank.plugins.Monitoring.collector import MonitoringCollector, \
    MonitoringDataListener, SSHWrapper
from yandextank.plugins.ConsoleOnline import Screen
from yandextank.plugins.Monitoring import MonitoringPlugin, MonitoringWidget
from ConsoleOnlinePluginTest import FakeConsoleMarkup
from TankTests import TankTestCase
import logging
import time
import tempfile


class  MonitoringCollectorTestCase(TankTestCase):
    data = None

    def test_collector(self):
        mon = MonitoringCollector()
        mon.config = "config/mon1.conf"
        mon.ssh_wrapper_class = SSHEmulator
        listener = TestMonListener()
        mon.add_listener(listener)
        mon.prepare()
        mon.start()
        mon.poll()

    def test_plugin_disabled(self):
        core = self.get_core()
        core.artifacts_base_dir = tempfile.mkdtemp()
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

    def test_plugin_default(self):
        core = self.get_core()
        core.artifacts_base_dir = tempfile.mkdtemp()
        core.load_configs(['config/monitoring.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        mon = MonitoringPlugin(core)
        mon.configure()
        mon.monitoring.ssh_wrapper_class = SSHEmulator
        mon.prepare_test()
        mon.start_test()
        self.assertEquals(-1, mon.is_test_finished())
        self.assertNotEquals(None, mon.monitoring)
        time.sleep(1)
        self.assertEquals(-1, mon.is_test_finished())
        mon.end_test(0)
        mon.post_process(0)

    def test_plugin_config(self):
        core = self.get_core()
        core.artifacts_base_dir = tempfile.mkdtemp()
        core.load_configs(['config/monitoring.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        mon = MonitoringPlugin(core)
        mon.monitoring.ssh_wrapper_class = SSHEmulator
        core.set_option(mon.SECTION, 'config', "config/mon1.conf")
        mon.configure()
        mon.prepare_test()
        mon.start_test()
        self.assertEquals(-1, mon.is_test_finished())
        self.assertNotEquals(None, mon.monitoring)
        time.sleep(1)
        self.assertEquals(-1, mon.is_test_finished())
        mon.end_test(0)
        mon.post_process(0)

    def test_plugin_config_with_username(self):
        core = self.get_core()
        core.artifacts_base_dir = tempfile.mkdtemp()
        core.load_configs(['config/monitoring.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        mon = MonitoringPlugin(core)
        mon.monitoring.ssh_wrapper_class = SSHEmulator
        core.set_option(mon.SECTION, 'config', "config/mon-user.conf")
        mon.configure()
        mon.prepare_test()
        mon.start_test()
        self.assertEquals(-1, mon.is_test_finished())
        self.assertNotEquals(None, mon.monitoring)
        time.sleep(1)
        self.assertEquals(-1, mon.is_test_finished())
        mon.end_test(0)
        mon.post_process(0)

    def test_plugin_inline_config(self):
        core = self.get_core()
        core.artifacts_base_dir = tempfile.mkdtemp()
        core.load_configs(['config/monitoring.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        mon = MonitoringPlugin(core)
        mon.monitoring.ssh_wrapper_class = SSHEmulator
        core.set_option(mon.SECTION, 'config', "<Monitoring>\n<Host address='[target]'/>\n</Monitoring>")
        mon.configure()
        mon.prepare_test()
        mon.start_test()
        self.assertEquals(-1, mon.is_test_finished())
        self.assertNotEquals(None, mon.monitoring)
        time.sleep(1)
        self.assertEquals(-1, mon.is_test_finished())
        mon.end_test(0)
        mon.post_process(0)
    
    def test_widget(self):
        core = self.get_core()
        core.artifacts_base_dir = tempfile.mkdtemp()
        owner = MonitoringPlugin(core)
        owner.monitoring = 1
        widget = MonitoringWidget(owner)
        screen = Screen(50, FakeConsoleMarkup())
        res = widget.render(screen)
        self.assertEquals("Monitoring is <g>online<rst>:", res)

        widget.monitoring_data("start;127.0.0.1;1347631472;Memory_total;Memory_used;Memory_free;Memory_shared;Memory_buff;Memory_cached;Net_recv;Net_send;")
        res = widget.render(screen)
        
        widget.monitoring_data("127.0.0.1;1347631473;1507.65625;576.9609375;8055;1518;0;143360;34.9775784753;16.1434977578;0.0")
        res = widget.render(screen)
        self.assertNotEquals("Monitoring is <g>online<rst>:", res)
        
        widget.monitoring_data("127.0.0.1;1347631473;1506.65625;574.9609375;8055;1518;0;143360;34.9775784753;16.1434977578;0.0")
        res = widget.render(screen)

    def test_plugin_default_failedInstall(self):
        core = self.get_core()
        core.artifacts_base_dir = tempfile.mkdtemp()
        core.load_configs(['config/monitoring.conf'])
        core.load_plugins()
        core.plugins_configure()
        core.plugins_prepare_test()
        mon = MonitoringPlugin(core)
        mon.configure()
        mon.monitoring.ssh_wrapper_class = SSHEmulatorFailer
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
        
class SSHEmulator(SSHWrapper):

    def __init__(self, timeout):
        SSHWrapper.__init__(self, timeout)
    
    def get_scp_pipe(self, cmd):
        self.scp_pipe = PipeEmul('data/ssh_out.txt', 'data/ssh_err.txt')
        return self.scp_pipe
    
    def get_ssh_pipe(self, cmd):
        self.ssh_pipe = PipeEmul('data/ssh_out.txt', 'data/ssh_err.txt')
        return self.ssh_pipe
    
class PipeEmul:
    def __init__(self, out, err):
        self.stderr = open(err, 'rU')
        self.stdout = open(out, 'rU')
        self.stdin = open(tempfile.mkstemp()[1], 'w')
        self.returncode = 0
        self.pid = 0
        
    def wait(self):
        pass
   
    def readline(self):
        return self.stdout.readline()
    
class SSHEmulatorFailer(SSHEmulator):
    def get_scp_pipe(self, cmd):
        raise RuntimeError()
    
    def get_ssh_pipe(self, cmd):
        raise RuntimeError()


