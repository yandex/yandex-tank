from Tank.Plugins.Stepper import Stepper
from Tests.TankTests import TankTestCase
import tempfile
import os

class  StepperTestCase(TankTestCase):
    data = None
    
    def test_regular(self):
        stepper = Stepper(tempfile.mkstemp()[1])
        stepper.ammofile = "data/dummy.ammo"
        stepper.rps_schedule = ["const(1,10)"]
        stepper.generate_stpd()
        res = open(stepper.stpd_file, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(269, os.path.getsize(stepper.stpd_file))

    def test_uri(self):
        stepper = Stepper(tempfile.mkstemp()[1])
        stepper.rps_schedule = ["const(1,10)"]
        stepper.uris = ["/", "/test"]
        stepper.header_http = "1.1"
        stepper.headers = ["[Host: ya.ru]", "[Connection: close]"]        
        stepper.generate_stpd()
        res = open(stepper.stpd_file, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(619, os.path.getsize(stepper.stpd_file))

    def test_free_inst_sched(self):
        stepper = Stepper(tempfile.mkstemp()[1])
        stepper.ammofile = "data/dummy.ammo"
        stepper.instances_schedule = "line(1,5,15)"
        stepper.loop_limit = 15        
        stepper.generate_stpd()
        res = open(stepper.stpd_file, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(406, os.path.getsize(stepper.stpd_file))

    def test_free_inst(self):
        stepper = Stepper(tempfile.mkstemp()[1])
        stepper.ammofile = "data/dummy.ammo"
        stepper.loop_limit = 2
        stepper.generate_stpd()
        res = open(stepper.stpd_file, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(56, os.path.getsize(stepper.stpd_file))
