from Tank.stepper import Stepper
from Tests.TankTests import TankTestCase
import tempfile
import os


class StepperTestCase(TankTestCase):
    data = None

    def test_regular(self, src_f_path='data/dummy.ammo'):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=["const(1,10)"],
                http_ver='1.1',
                ammo_file=src_f_path,
                instances_schedule=[],
                loop_limit=-1,
                ammo_limit=-1,
                uris=[],
                headers=[],
                autocases=0,
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        # ensure that we got a valid stpd file here
        self.assertEquals(317, os.path.getsize(temp_stpd))

    def test_regular_gziped(self, src_f_path='data/dummy-ammo-compressed.gz'):
        """ Call stepper on dummy HTTP ammo file with 1 req.
            Source ammo file compressed  with gzip 1.4 lib.
        """
        return self.test_regular(src_f_path=src_f_path)

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
