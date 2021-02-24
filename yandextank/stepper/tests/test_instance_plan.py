import io
import os
import threading

import pytest

from yandextank.common.interfaces import TankInfo
from yandextank.common.util import get_test_path, read_resource
from yandextank.core import TankCore
from yandextank.stepper import Stepper
from yandextank.stepper.instance_plan import LoadPlanBuilder, create

from yandextank.stepper.util import take


class TestCreate(object):
    @pytest.mark.parametrize(
        'n, loadplan, expected',
        [(
            7, LoadPlanBuilder().ramp(5, 4000).create(),
            [0, 1000, 2000, 3000, 4000, 0, 0]
        ), (
            7, create(['ramp(5, 4s)']),
            [0, 1000, 2000, 3000, 4000, 0, 0]
        ), (
            12, create(['ramp(5, 4s)', 'wait(5s)', 'ramp(5,4s)']),
            [0, 1000, 2000, 3000, 4000, 9000, 10000, 11000, 12000, 13000, 0, 0]
        ), (
            7, create(['wait(5s)', 'ramp(5, 0)']),
            [5000, 5000, 5000, 5000, 5000, 0, 0]
        ), (
            7, create([]),
            [0, 0, 0, 0, 0, 0, 0]
        ), (
            12, create(['line(1, 9, 4s)']),
            [0, 500, 1000, 1500, 2000, 2500, 3000, 3500, 4000, 0, 0, 0]
        ), (
            12, create(['const(3, 5s)', 'line(7, 11, 2s)']),
            [0, 0, 0, 5000, 5000, 5000, 5000, 5500, 6000, 6500, 7000, 0]
        ), (
            12, create(['step(2, 10, 2, 3s)']),
            [0, 0, 3000, 3000, 6000, 6000, 9000, 9000, 12000, 12000, 0, 0]
        ), (
            12, LoadPlanBuilder().const(3, 1000).line(5, 10, 5000).steps,
            [(3, 1), (5, 1), (6, 1), (7, 1), (8, 1), (9, 1), (10, 1)]
        ), (
            12, LoadPlanBuilder().stairway(100, 950, 100, 30000).steps,
            [
                (100, 30), (200, 30), (300, 30), (400, 30), (500, 30),
                (600, 30), (700, 30), (800, 30), (900, 30), (950, 30)]
        )])  # yapf:disable
    def test_steps(self, n, loadplan, expected):
        assert take(n, loadplan) == expected

    @pytest.mark.parametrize(
        'loadplan, expected',
        [(LoadPlanBuilder().stairway(100, 950, 100, 30000), 950),
         (LoadPlanBuilder().const(3, 1000).line(5, 10, 5000), 10),
         (LoadPlanBuilder().line(1, 100, 60000), 100)])
    def test_instances(self, loadplan, expected):
        assert loadplan.instances == expected


@pytest.mark.parametrize('stepper_kwargs, expected_stpd', [
    ({'uris': ['/'],
      'instances_schedule': ['line(1,11,5s)'],
      'instances': 11,
      },
     'yandextank/stepper/tests/instances1.stpd'),
])
def test_plan(stepper_kwargs, expected_stpd):
    stepper = Stepper(
        TankCore([{}], threading.Event(), TankInfo({})),
        http_ver="1.1",
        loop_limit=15,
        ammo_limit=1000,
        enum_ammo=False,
        **stepper_kwargs
    )
    stepper_output = io.BytesIO()
    stepper.write(stepper_output)
    stepper_output.seek(0)
    expected_lines = read_resource(os.path.join(get_test_path(), expected_stpd), 'rb').split(b'\n')
    for i, (result, expected) in enumerate(zip(stepper_output, expected_lines)):
        assert result.strip() == expected.strip(), 'Line {} mismatch'.format(i)
