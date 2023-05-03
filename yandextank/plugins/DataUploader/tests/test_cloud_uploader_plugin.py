from yandextank.plugins.DataUploader.client import CloudGRPCClient
from yandex.cloud.loadtesting.agent.v1 import monitoring_service_pb2


SAMPLE_MONITORING_METRICS_JSON = {
    "Memory_buff": 1026465792,
    "custom:mem_commit_limit": 33079422976,
    "custom:cpu-cpu-total_usage_idle": 96.79043423670709,
    "System_la5": 1.12,
    "custom:cpu-cpu4_usage_system": 0.9999999999308784,
    "custom:mem_high_free": 0,
    "custom:network_message": "connection ok",
}
SAMPLE_MONITORING_DATA_JSON = [{
    "timestamp": 1663666609,
    "data": {
        "localhost": {
            "comment": "some comment",
            "metrics": {
                "System_la5": 1.12,
                "custom:network_message": "connection ok",
            },
        }
    }
}, {
    "timestamp": 1663666609,
    "data": {
        "localhost": {
            "comment": "some comment",
            "metrics": {
                "custom:mem_commit_limit": 33079422976,
            },
        }
    }
}]


class TestMonitoringDataConverters(object):

    def test_json_metric_to_proto_message__correct_json_parse(self):

        expected = [monitoring_service_pb2.Metric(
            metric_type='Memory',
            metric_name='buff',
            metric_value=1026465792,
        ), monitoring_service_pb2.Metric(
            metric_type='mem',
            metric_name='commit_limit',
            metric_value=33079422976,
        ), monitoring_service_pb2.Metric(
            metric_type='cpu-cpu-total',
            metric_name='usage_idle',
            metric_value=96.79043423670709,
        ), monitoring_service_pb2.Metric(
            metric_type='System',
            metric_name='la5',
            metric_value=1.12,
        ), monitoring_service_pb2.Metric(
            metric_type='cpu-cpu4',
            metric_name='usage_system',
            metric_value=0.9999999999308784,
        ), monitoring_service_pb2.Metric(
            metric_type='mem',
            metric_name='high_free',
            metric_value=0,
        ), monitoring_service_pb2.Metric(
            metric_type='network',
            metric_name='message',
            metric_value=0,
        )]

        metrics = CloudGRPCClient._json_metric_to_proto_message(SAMPLE_MONITORING_METRICS_JSON)

        assert expected == metrics

    def test_json_monitoring_data_item_to_proto_request_messages__correct_json_parse(self):

        expected = [monitoring_service_pb2.MetricChunk(
            timestamp=1663666609,
            comment="some comment",
            instance_host="localhost",
            data=[monitoring_service_pb2.Metric(
                metric_type='System',
                metric_name='la5',
                metric_value=1.12,
            ), monitoring_service_pb2.Metric(
                metric_type='network',
                metric_name='message',
                metric_value=0,
            ), monitoring_service_pb2.Metric(
                metric_type='mem',
                metric_name='commit_limit',
                metric_value=33079422976,
            )]
        )]

        requests = CloudGRPCClient._json_monitoring_data_item_to_proto_metric_chunks(SAMPLE_MONITORING_DATA_JSON)
        assert expected == requests
