import pandas as pd

from yandextank.plugins.Phantom.reader import PhantomReader, PhantomStatsReader


class TestPhantomReader(object):
    def test_read_all(self):
        reader = PhantomReader(
            'yandextank/plugins/Phantom/tests/phout.dat', cache_size=1024)
        df = pd.DataFrame()
        for chunk in reader:
            if chunk is None:
                reader.close()
            else:
                df = df.append(chunk)
        assert (len(df) == 200)
        assert (df['interval_real'].mean() == 11000714.0)

    def test_reader_closed(self):
        reader = PhantomReader('yandextank/plugins/Phantom/tests/phout.dat', cache_size=64)
        reader.close()
        frames = [i for i in reader]
        result = pd.concat(frames)
        assert len(result) == 200
        assert (result['interval_real'].mean() == 11000714.0)


class MockInfo(object):
    def __init__(self, steps):
        self.steps = steps


class TestStatsReader(object):

    def test_closed(self):
        STEPS = [[1.0, 1], [1.0, 1], [1.0, 1], [2.0, 1], [2.0, 1], [2.0, 1], [2.0, 1], [2.0, 1], [3.0, 1], [3.0, 1],
                 [3.0, 1], [3.0, 1], [3.0, 1], [4.0, 1], [4.0, 1], [4.0, 1], [4.0, 1], [4.0, 1], [5.0, 1], [5.0, 1],
                 [5.0, 1]]
        reader = PhantomStatsReader('yandextank/plugins/Phantom/tests/phantom_stat.dat',
                                    MockInfo(STEPS), cache_size=1024*10)
        reader.close()
        stats = reduce(lambda l1, l2: l1 + l2, [i for i in reader])

        assert len(stats) == 19
