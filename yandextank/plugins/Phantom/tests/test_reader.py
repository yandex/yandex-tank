from threading import Event
import os
import pandas as pd

from yandextank.common.util import FileMultiReader
from yandextank.plugins.Phantom.reader import PhantomReader, PhantomStatsReader, string_to_df_microsec
try:
    from yatest import common
    PATH = common.source_path('load/projects/yandex-tank/yandextank/plugins/Phantom/tests')
except ImportError:
    PATH = os.path.dirname(__file__)


class TestPhantomReader(object):
    def setup_class(self):
        stop = Event()
        self.multireader = FileMultiReader(os.path.join(PATH, 'phout.dat'), stop)
        stop.set()

    def teardown_class(self):
        self.multireader.close()

    def test_read_all(self):
        reader = PhantomReader(
            self.multireader.get_file(), cache_size=1024)
        df = pd.DataFrame()
        for chunk in reader:
            df = df.append(chunk)
        assert (len(df) == 200)
        assert (df['interval_real'].mean() == 11000714.0)

    def test_reader_closed(self):
        reader = PhantomReader(self.multireader.get_file(), cache_size=64)
        frames = [i for i in reader]
        result = pd.concat(frames)
        assert len(result) == 200
        assert (result['interval_real'].mean() == 11000714.0)

    def test_reader_us(self):
        with open(os.path.join(PATH, 'phout.dat')) as f:
            chunk = f.read()
        result = string_to_df_microsec(chunk)
        expected = pd.read_pickle(os.path.join(PATH, 'expected_df.dat'))
        result['ts'] -= result['ts'][0]
        assert result.equals(expected)


class MockInfo(object):
    def __init__(self, steps):
        self.steps = steps


class TestStatsReader(object):

    def test_closed(self):
        STEPS = [[1.0, 1], [1.0, 1], [1.0, 1], [2.0, 1], [2.0, 1], [2.0, 1], [2.0, 1], [2.0, 1], [3.0, 1], [3.0, 1],
                 [3.0, 1], [3.0, 1], [3.0, 1], [4.0, 1], [4.0, 1], [4.0, 1], [4.0, 1], [4.0, 1], [5.0, 1], [5.0, 1],
                 [5.0, 1]]
        reader = PhantomStatsReader(os.path.join(PATH, 'phantom_stat.dat'),
                                    MockInfo(STEPS), cache_size=1024 * 10)
        reader.close()
        stats = reduce(lambda l1, l2: l1 + l2, [i for i in reader])

        assert len(stats) == 19
