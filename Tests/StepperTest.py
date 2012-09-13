from Tank.Plugins.Stepper import Stepper
from Tests.TankTests import TankTestCase
import tempfile

class  StepperTestCase(TankTestCase):
    data = None
    
    def test_regular(self):
        stepper = Stepper()
        stepper.ammofile = "data/dummy.ammo"
        stepper.rps_schedule = "const(1,10)"
        stepper.stpd_file = tempfile.mkstemp()[1]        
        stepper.main()

    def test_uri(self):
        stepper = Stepper()
        stepper.rps_schedule = "const(1,10)"
        stepper.stpd_file = tempfile.mkstemp()[1]
        stepper.uris=["/", "/test"]
        stepper.header_http="1.1"
        stepper.headers=["[Host: ya.ru]", "[Connection: close]"]        
        stepper.main()

    def test_free_inst_sched(self):
        stepper = Stepper()
        stepper.ammofile = "data/dummy.ammo"
        stepper.instances_schedule = "const(1,10)"
        stepper.stpd_file = tempfile.mkstemp()[1]
        stepper.main()

    def test_free_inst(self):
        stepper = Stepper()
        stepper.ammofile = "data/dummy.ammo"
        stepper.loop_limit = 2
        stepper.stpd_file = tempfile.mkstemp()[1]
        stepper.main()
