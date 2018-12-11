import pytest
from yandextank.stepper.load_plan import create, Const, Line, Composite, Stairway, StepFactory
from yandextank.stepper.util import take


class TestLine(object):
    def test_get_rps_list(self):
        lp = create(["line(1, 100, 10s)"])
        rps_list = lp.get_rps_list()
        assert len(rps_list) == 11
        assert rps_list[-1][0] == 100


@pytest.mark.parametrize(
    "rps, duration, rps_list",
    [(100, 3000, [(100, 3)]), (0, 3000, [(0, 3)]), (100, 0, [(100, 0)])])
class TestConst(object):
    @pytest.mark.parametrize(
        "check_point, expected",
        [(lambda duration: 0, lambda rps: rps),
         (lambda duration: duration / 2, lambda rps: rps),
         (lambda duration: duration + 1, lambda rps: 0),
         (lambda duration: -1, lambda rps: 0)])
    def test_rps_at(self, rps, duration, rps_list, check_point, expected):
        assert Const(rps,
                     duration).rps_at(check_point(duration)) == expected(rps)

    def test_get_rps_list(self, rps, duration, rps_list):
        assert Const(rps, duration).get_rps_list() == rps_list
        assert isinstance(rps_list[0][1], int)


class TestLineNew(object):
    @pytest.mark.parametrize(
        "min_rps, max_rps, duration, check_point, expected",
        [(0, 10, 30 * 1000, 0, 0), (0, 10, 30 * 1000, 10, 3),
         (0, 10, 30 * 1000, 29, 10), (9, 10, 30 * 1000, 1, 9),
         (9, 10, 30 * 1000, 20, 10)])
    def test_rps_at(self, min_rps, max_rps, duration, check_point, expected):
        assert round(Line(min_rps, max_rps, duration).rps_at(
            check_point)) == expected

    @pytest.mark.parametrize(
        "min_rps, max_rps, duration, check_point, expected",
        [
            (0, 10, 20 * 1000, 9, (9, 2)),
            (0, 10, 30 * 1000, 0, (0, 2)),
            (0, 10, 30 * 1000, 5, (5, 3)),
            (0, 10, 30 * 1000, 10, (10, 2)),
            (0, 10, 3 * 1000, 0, (0, 1)),
            (0, 10, 3 * 1000, 1, (3, 1)),
            (0, 10, 3 * 1000, 2, (7, 1)),
            (0, 10, 3 * 1000, 3, (10, 1)),
            (9, 10, 30 * 1000, 0, (9, 15)),
            (9, 10, 30 * 1000, 1, (10, 16)),
            (10, 10, 30 * 1000, 0, (10, 31)),  # strange
            (10, 0, 30 * 1000, 0, (10, 2)),
            (10, 0, 30 * 1000, 1, (9, 3)),
            (10, 0, 30 * 1000, 9, (1, 3)),
            (10, 0, 30 * 1000, 10, (0, 2)),
        ])
    def test_get_rps_list(
            self, min_rps, max_rps, duration, check_point, expected):
        assert Line(min_rps, max_rps,
                    duration).get_rps_list()[check_point] == expected

    @pytest.mark.parametrize(
        "min_rps, max_rps, duration, expected_len, threshold, len_above_threshold",
        [
            (2, 12, 25000, 175, 5000, 160),
            (2, 12, 25000, 175, 10000, 135),
            (2, 12, 25000, 175, 15000, 100),
            (2, 12, 25000, 175, 20000, 55),
            (0, 10, 25000, 125, 15000, 80),
            (10, 12, 20000, 220, 10000, 115),
            (10, 10, 20000, 200, 10000, 100),
            (10, 0, 25000, 125, 10000, 45),
            (10, 0, 25000, 125, 15000, 20),
        ])
    def test_iter(
            self, min_rps, max_rps, duration, expected_len, threshold,
            len_above_threshold):
        load_plan = Line(min_rps, max_rps, duration)
        assert len(load_plan) == expected_len
        assert len(
            [ts for ts in load_plan if ts >= threshold]) == len_above_threshold


class TestComposite(object):
    @pytest.mark.parametrize(
        "steps, expected_len", [([Line(0, 10, 20000), Const(10, 10000)], 200),
                                ([Line(0, 10, 20000), Line(10, 0, 20000)], 200),
                                ([Const(5, 10000), Const(10, 5000)], 100)])
    def test_iter(self, steps, expected_len):
        assert len(Composite(steps)) == expected_len

    @pytest.mark.parametrize(
        "steps, check_point, expected", [
            ([Line(0, 10, 20000), Const(10, 10000)], 9, (9, 2)),
            ([Line(0, 10, 20000), Const(10, 10000)], 10, (10, 2)),
            ([Line(0, 10, 20000), Const(10, 10000)], 11, (10, 10)),
        ])
    def test_rps_list(self, steps, check_point, expected):
        assert Composite(steps).get_rps_list()[check_point] == expected


class TestStairway(object):
    @pytest.mark.parametrize(
        "min_rps, max_rps, increment, step_duration, expected_len, threshold, len_above_threshold",
        [(0, 1000, 50, 3000, 31500, 9000, 31050),
         (0, 1000, 50, 3000, 31500, 15000, 30000),
         (0, 1000, 50, 3000, 31500, 45000, 15750)])
    def test_iter(
            self, min_rps, max_rps, increment, step_duration, expected_len,
            threshold, len_above_threshold):
        load_plan = Stairway(min_rps, max_rps, increment, step_duration)
        assert len(load_plan) == expected_len
        assert len(
            [ts for ts in load_plan if ts >= threshold]) == len_above_threshold


class TestCreate(object):
    @pytest.mark.parametrize(
        'rps_schedule, check_point, expected', [
            (['line(1, 5, 2s)'], 100, [0, 618, 1000, 1302, 1561, 1791]),
            (['line(1.1, 5.8, 2s)'], 100, [0, 566, 917, 1196, 1435, 1647]),
            (['line(5, 1, 2s)'], 100, [0, 208, 438, 697, 1000, 1381]),
            (['const(1, 10s)'], 100,
             [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000]),
            (['const(200, 0.1s)'], 100, [
                0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75,
                80, 85, 90, 95
            ]),
            (['const(1, 2s)', 'const(2, 2s)'], 100,
             [0, 1000, 2000, 2500, 3000, 3500]),
            (['const(1.5, 10s)'], 100, [
                0, 666, 1333, 2000, 2666, 3333, 4000, 4666, 5333, 6000, 6666,
                7333, 8000, 8666, 9333
            ]),
            (['step(1, 5, 1, 5s)'], 10,
             [0, 1000, 2000, 3000, 4000, 5000, 5500, 6000, 6500, 7000]),
            (['step(1.2, 5.7, 1.1, 5s)'], 10,
             [0, 833, 1666, 2500, 3333, 4166, 5000, 5434, 5869, 6304]),
            (['const(1, 1)'], 10, [0]),
        ])
    def test_create(self, rps_schedule, check_point, expected):
        # pytest.set_trace()
        assert take(check_point, (create(rps_schedule))) == expected


# ([0-9.]+d)?([0-9.]+h)?([0-9.]+m)?([0-9.]+s)?
@pytest.mark.parametrize('step_config, expected_duration', [
    ('line(1,500,1m30s)', 90),
    ('const(50,1h30s)', 3630 * 1000),
    ('step(10,200,10,1h20m)', 4800 * 1000)
])
def test_step_factory(step_config, expected_duration):
    steps = StepFactory.produce(step_config)
    assert steps.duration == expected_duration
