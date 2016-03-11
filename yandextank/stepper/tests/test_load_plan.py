from yandextank.stepper.load_plan import create


class TestLine(object):
    def test_get_rps_list(self):
        lp = create(["line(1, 100, 10s)"])
        rps_list = lp.get_rps_list()
        assert len(rps_list) == 11
        assert rps_list[-1][0] == 100
