import tempfile
import os

from yandextank.stepper import Stepper
from yandextank.stepper.format import StpdReader
from TankTests import TankTestCase


class StepperTestCase(TankTestCase):
    data = None

    def test_regular(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=["const(1,10)"],
                http_ver='1.1',
                ammo_file='data/dummy.ammo',
                instances_schedule=[],
                loop_limit=-1,
                ammo_limit=-1,
                uris=[],
                headers=[],
                autocases=0,
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(277, os.path.getsize(temp_stpd))

    def test_regular_gziped(self):
        """ Call stepper on dummy HTTP ammo file with 1 req.
            Source ammo file compressed  with gzip 1.4 lib.
        """
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=["const(1,10)"],
                http_ver='1.1',
                ammo_file='data/dummy-ammo-compressed.gz',
                instances_schedule=[],
                loop_limit=-1,
                ammo_limit=-1,
                uris=[],
                headers=[],
                autocases=0,
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(277, os.path.getsize(temp_stpd))

    def test_uri(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=["const(1,10)"],
                http_ver='1.1',
                instances_schedule=[],
                loop_limit=-1,
                ammo_limit=-1,
                uris=["/", "/test"],
                headers=["[Host: ya.ru]", "[Connection: close]"],
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(657, os.path.getsize(temp_stpd))

    def test_uri_style(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=["const(1,10)"],
                http_ver='1.1',
                ammo_file="data/uri.ammo",
                instances_schedule=[],
                loop_limit=-1,
                ammo_limit=-1,
                headers=["[Host: ya.ru]", "[Connection: close]"],
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(1567, os.path.getsize(temp_stpd))

    def test_free_inst_sched(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=[],
                http_ver='1.1',
                instances_schedule=["line(1,5,15)"],
                loop_limit=15,
                ammo_limit=-1,
                uris=["/", "/test"],
                headers=["[Host: ya.ru]", "[Connection: close]"],
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(1904, os.path.getsize(temp_stpd))


    def test_manual_inst(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                instances=20000,
                rps_schedule=["line(1,5,15)"],
                http_ver='1.1',
                uris=["/", "/test"],
                headers=["[Host: ya.ru]", "[Connection: close]"],
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(2985, os.path.getsize(temp_stpd))


    def test_free_inst(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=[],
                http_ver='1.1',
                instances_schedule=["line(1,5,15)"],
                loop_limit=2,
                ammo_limit=-1,
                uris=["/", "/test"],
                headers=["[Host: ya.ru]", "[Connection: close]"],
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(262, os.path.getsize(temp_stpd))

    def test_default(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=[],
                http_ver='1.1',
                instances_schedule=[],
                loop_limit=-1,
                ammo_limit=-1,
                uris=["/", "/test"],
                headers=["[Host: ya.ru]", "[Connection: close]"],
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(126, os.path.getsize(temp_stpd))

    def test_access_log(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=[],
                instances_schedule=[],
                loop_limit=-1,
                ammo_limit=10,
                ammo_type='access',
                headers=[],
                ammo_file="data/access1.log",
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(1459, os.path.getsize(temp_stpd))

    def test_empty_uri(self):
        from yandextank.stepper.module_exceptions import AmmoFileError
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            with self.assertRaises(AmmoFileError):
                Stepper(
                    rps_schedule=[],
                    instances_schedule=[],
                    loop_limit=-1,
                    ammo_limit=10,
                    headers=[],
                    ammo_file="data/empty.uri",
                ).write(stpd_file)

    def test_chosen_cases(self):
        temp_stpd = tempfile.mkstemp()[1]
        with open(temp_stpd, 'w') as stpd_file:
            Stepper(
                rps_schedule=["const(1, 10)"],
                loop_limit=-1,
                ammo_limit=10,
                uris=["/one", "/two"],
                autocases=1,
                headers=["[Connection: close]"],
                chosen_cases="_one",
            ).write(stpd_file)
        res = open(temp_stpd, 'r').read()
        self.assertNotEquals("", res)
        self.assertEquals(res.count('_two'), 0)
        self.assertEquals(res.count('_one'), 10)

    def test_stpd_reader(self):
        sr = StpdReader("data/dummy.ammo.stpd")
        self.assertEquals(len(list(sr)), 10)

    def test_bad_stpd_reader(self):
        from yandextank.stepper.module_exceptions import StpdFileError
        sr = StpdReader("data/bad.ammo.stpd")
        with self.assertRaises(StpdFileError):
            list(sr)
