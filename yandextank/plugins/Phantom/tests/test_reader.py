import pandas as pd

from yandextank.plugins.Phantom.reader import PhantomReader


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
