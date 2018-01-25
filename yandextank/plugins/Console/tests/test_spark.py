# -*- coding: utf-8 -*-
import time
from yandextank.plugins.Console.screen import Sparkline


class TestSparkline(object):
    def test_unusual_vals(self):
        data = [0, 1, -100, 0.1, 1000, -0.1, 50]
        expected = ' _ _▇ _'.decode('utf-8')
        sparkline = Sparkline(len(data))
        start = int(time.time()) - len(data)
        for num, val in enumerate(data):
            sparkline.add(start + num, 'data', val)
        spark = ''.join(sparkline.get_sparkline('data'))
        assert (len(spark) == len(data))
        assert (spark == expected)
        zero = sparkline.get_sparkline('continous', spark_len=0)
        assert (len(zero) == 0)
        negative = sparkline.get_sparkline('continous', spark_len=-1)
        assert (len(negative) == 0)

    def test_non_continuos(self):
        data = range(20)
        expected = ' _▁▂▃▄▅▆▇    ▃▄▅▆▇ _'.decode('utf-8')
        expected_short = '▆▇ _'.decode('utf-8')
        expected_long = '     _▁▂▃▄▅▆▇    ▃▄▅▆▇ _'.decode('utf-8')
        spark_len = 24
        sparkline = Sparkline(spark_len)
        start = int(time.time()) - len(data)
        for num, val in enumerate(data):
            if val <= 8 or val > 12:
                sparkline.add(start + num, 'data', val % 9)
        spark = ''.join(sparkline.get_sparkline('data', spark_len=len(data)))
        assert (spark == expected)
        short_spark = ''.join(sparkline.get_sparkline('data', spark_len=4))
        assert (short_spark == expected_short)
        long_spark = ''.join(sparkline.get_sparkline('data'))
        assert (long_spark == expected_long)

    def test_multi_graphs(self):
        expected_continous = '__▁▁▂▂▃▃▄▄▅▅▆▆▇▇'.decode('utf-8')
        expected_spotty = '_ ▁ ▂ ▃ ▄ ▅ ▆ ▇ '.decode('utf-8')
        continous_vals = range(1, 17)
        sparkline = Sparkline(len(continous_vals))
        start = int(time.time()) - len(continous_vals)
        for val in continous_vals:
            sparkline.add(start + val, 'continous', val)
            if val % 2 == 1:
                sparkline.add(start + val, 'spotty', val)
        continous = ''.join(sparkline.get_sparkline('continous'))
        spotty = ''.join(sparkline.get_sparkline('spotty'))
        assert (continous == expected_continous)
        assert (spotty == expected_spotty)
