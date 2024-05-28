from threading import Event
import os

import pandas as pd
from yandextank.common.util import get_test_path
from yandextank.common.util import FileMultiReader
from yandextank.plugins.ShootExec.plugin import _ShootExecReader, PhantomReader, DataPoller


class TestPhantomReader(object):
    def setup_class(self):
        stop = Event()
        self.multireader = FileMultiReader(os.path.join(get_test_path(), 'yandextank/plugins/ShootExec/tests/phout.dat'), stop)
        stop.set()

    def teardown_class(self):
        self.multireader.close()

    def test_read_all(self):
        phantom_reader = PhantomReader(
            self.multireader.get_file(), cache_size=1024)
        reader = _ShootExecReader(phantom_reader, DataPoller(poll_period=.1, max_wait=2))
        df = pd.DataFrame()
        sdf = pd.DataFrame()
        for chunk in reader:
            df = pd.concat([df, pd.DataFrame.from_records(chunk)])
        for stat_items in reader.stats_reader:
            sdf = pd.concat([sdf, pd.DataFrame.from_records(stat_items)])
        assert len(df) == 200
        assert df['interval_real'].mean() == 11000714.0
        assert len(sdf['ts'].unique()) == 12
        assert sdf['ts'].min() == 1482159938
        assert sdf['ts'].max() == 1482159949
