# -*- coding: utf-8 -*-
from uuid import uuid4

from yandextank.plugins.OpenTSDBUploader.decoder import Decoder


class TestDecoder(object):
    def test_metrics_cast(self):
        test_uuid = str(uuid4())
        tank_tag = 'test_tank_tag'
        comment = 'test comment'
        raw_metrics = {
            'metric1': -123,
            'metric2': -123.456,
            'metric3': 123,
            'metric4': 123.456,
            'metric5': 0,
            'metric6': -0.1,
            'metric7': 0.1,
            'metric8': 'down',
        }
        timestamp = 123456789
        host = '127.0.0.1'
        data = [{
            'data': {
                host: {
                    'comment': comment,
                    'metrics': raw_metrics
                }
            },
            'timestamp': timestamp
        }]
        expected_metrics = {
            'metric1': -123.0,
            'metric2': -123.456,
            'metric3': 123.0,
            'metric4': 123.456,
            'metric5': 0.0,
            'metric6': -0.1,
            'metric7': 0.1,
            'metric8': 'down'
        }

        decoder = Decoder(tank_tag, test_uuid, {}, True, True)
        result_points = decoder.decode_monitoring(data)

        assert (len(result_points) == len(expected_metrics))
        # check other props
        for r_point in result_points:
            assert (r_point['timestamp'] == timestamp)
            assert (r_point['metric'] == 'monitoring')
            assert (r_point['tags']['comment'] == comment)
            assert (r_point['tags']['host'] == host)
            assert (r_point['tags']['tank'] == tank_tag)
            assert (r_point['tags']['uuid'] == test_uuid)
            if r_point['tags']['field'] not in expected_metrics:
                assert False
            if not isinstance(r_point['value'], type(
                    expected_metrics[r_point['tags']['field']])):
                assert False
            if not r_point['value'] == expected_metrics[r_point['tags']
                                                        ['field']]:
                assert False
