import threading
from queue import Queue
import time
import pytest
from mock import patch, call, MagicMock
from requests import ConnectionError
from yandextank.plugins.DataUploader.client import APIClient

from yandextank.plugins.DataUploader.plugin import online_uploader, LPJob


@pytest.mark.parametrize('job_number, token', [
    (42, 'fooToken'),
    (314, 'tokenBar')
])
class TestOnlineUploader(object):

    def test_with_job_number(self, job_number, token):
        data_set = ['data%d' % i for i in range(100)]

        queue = Queue()
        job = LPJob(job_number, token)

        with patch.object(APIClient, 'push_data') as push_data_mock:

            thread = threading.Thread(
                target=online_uploader,
                name='Online uploader',
                args=(queue, job))
            thread.daemon = True
            thread.start()

            for data in data_set:
                if job.is_alive:
                    queue.put(data)
                else:
                    break
            time.sleep(1)
            push_data_mock.assert_has_calls(
                calls=[
                    call(
                        data,
                        job_number,
                        token) for data in data_set])

    def test_without_job_number(self, job_number, token):
        data_set = ['data%d' % i for i in range(100)]

        queue = Queue()
        job = LPJob()

        with patch.object(APIClient, 'new_job', return_value=(job_number, token)) as new_job_mock:
            with patch.object(APIClient, 'push_data') as push_data_mock:

                thread = threading.Thread(
                    target=online_uploader,
                    name='Online uploader',
                    args=(
                        queue,
                        job))
                thread.daemon = True
                thread.start()

                for data in data_set:
                    if job.is_alive:
                        queue.put(data)
                    else:
                        break
                time.sleep(1)
                new_job_mock.assert_called_once_with(*[None] * 8)
                push_data_mock.assert_has_calls(
                    calls=[call(data, job_number, token) for data in data_set])


@pytest.mark.parametrize('job_nr, upload_token', [
    ('101', 'hfh39fj'),
])
class TestClient(object):
    TEST_DATA = {'tagged': {'case1': {u'size_in': {u'max': 0, u'total': 0, u'len': 4, u'min': 0},
                                      u'latency': {u'max': 0, u'total': 0, u'len': 4, u'min': 0}, u'interval_real': {
        u'q': {'q': [50, 75, 80, 85, 90, 95, 98, 99, 100],
               'value': [484467.0, 688886.75, 736398.80000000005, 783910.84999999998, 831422.90000000002,
                         878934.94999999995, 907442.17999999993, 916944.58999999985, 926447.0]}, u'min': 196934,
        u'max': 926447, u'len': 4,
        u'hist': {'data': [1, 1, 1, 1], 'bins': [197000.0, 360000.0, 610000.0, 930000.0]}, u'total': 2092315},
        u'interval_event': {u'max': 0, u'total': 0, u'len': 4, u'min': 0},
        u'receive_time': {u'max': 0, u'total': 0, u'len': 4, u'min': 0},
        u'connect_time': {u'max': 0, u'total': 0, u'len': 4, u'min': 0},
        u'proto_code': {u'count': {'200': 4}},
        u'size_out': {u'max': 0, u'total': 0, u'len': 4, u'min': 0},
        u'send_time': {u'max': 0, u'total': 0, u'len': 4, u'min': 0},
        u'net_code': {u'count': {'0': 4}}},
        'default': {u'size_in': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
                    u'latency': {u'max': 0, u'total': 0, u'len': 3, u'min': 0}, u'interval_real': {
            u'q': {'q': [50, 75, 80, 85, 90, 95, 98, 99, 100],
                   'value': [247863.0, 419279.5, 453562.80000000005, 487846.09999999998,
                             522129.40000000002, 556412.69999999995, 576982.68000000005,
                             583839.33999999997, 590696.0]}, u'min': 128669, u'max': 590696,
            u'len': 3, u'hist': {'data': [1, 1, 1], 'bins': [129000.0, 248000.0, 595000.0]},
            u'total': 967228},
        u'interval_event': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'receive_time': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'connect_time': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'proto_code': {u'count': {'200': 3}},
        u'size_out': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'send_time': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'net_code': {u'count': {'0': 3}}},
        'case2': {u'size_in': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
                  u'latency': {u'max': 0, u'total': 0, u'len': 3, u'min': 0}, u'interval_real': {
            u'q': {'q': [50, 75, 80, 85, 90, 95, 98, 99, 100],
                   'value': [366638.0, 431245.0, 444166.40000000002, 457087.79999999999,
                             470009.20000000001, 482930.59999999998, 490683.44,
                             493267.71999999997, 495852.0]}, u'min': 328929, u'max': 495852,
            u'len': 3, u'hist': {'data': [1, 1, 1], 'bins': [329000.0, 367000.0, 496000.0]},
            u'total': 1191419},
        u'interval_event': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'receive_time': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'connect_time': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'proto_code': {u'count': {'200': 3}},
        u'size_out': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'send_time': {u'max': 0, u'total': 0, u'len': 3, u'min': 0},
        u'net_code': {u'count': {'0': 3}}}},
        'overall': {u'size_in': {u'max': 0, u'total': 0, u'len': 10, u'min': 0},
                    u'latency': {u'max': 0, u'total': 0, u'len': 10, u'min': 0}, u'interval_real': {
            u'q': {'q': [50, 75, 80, 85, 90, 95, 98, 99, 100],
                   'value': [362936.0, 566985.0, 594496.79999999993, 603048.59999999998,
                             641374.69999999995, 783910.84999999963, 869432.54000000004,
                             897939.77000000002, 926447.0]}, u'min': 128669, u'max': 926447, u'len': 10,
            u'hist': {'data': [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                      'bins': [129000.0, 197000.0, 248000.0, 329000.0, 360000.0, 367000.0, 496000.0,
                               595000.0, 610000.0, 930000.0]}, u'total': 4250962},
        u'interval_event': {u'max': 0, u'total': 0, u'len': 10, u'min': 0},
        u'receive_time': {u'max': 0, u'total': 0, u'len': 10, u'min': 0},
        u'connect_time': {u'max': 0, u'total': 0, u'len': 10, u'min': 0},
        u'proto_code': {u'count': {'200': 10}},
        u'size_out': {u'max': 0, u'total': 0, u'len': 10, u'min': 0},
        u'send_time': {u'max': 0, u'total': 0, u'len': 10, u'min': 0},
        u'net_code': {u'count': {'0': 10}}}, 'ts': 1476377527}
    TEST_STATS = {'metrics': {'instances': 0, 'reqps': 0}, 'ts': 1476446024}

    def test_new_job(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/')
        with patch('requests.Session.send') as send_mock:
            mock_response = MagicMock()
            mock_response.json.return_value = [
                {"upload_token": upload_token, "job": job_nr}]
            send_mock.return_value = mock_response
            assert client.new_job(
                'LOAD-204',
                'fomars',
                'tank',
                'target.host',
                1234) == (
                job_nr,
                upload_token)

    def test_new_job_retry_maintenance(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/',
            maintenance_timeout=2)
        with patch('requests.Session.send') as send_mock:
            bad_response = MagicMock()
            bad_response.status_code = 423
            good_response = MagicMock()
            good_response.json.return_value = [
                {"upload_token": upload_token, "job": job_nr}]
            send_mock.side_effect = [bad_response, good_response]

            assert client.new_job(
                'LOAD-204',
                'fomars',
                'tank',
                'target.host',
                1234) == (
                job_nr,
                upload_token)

    def test_new_job_retry_network(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/')
        with patch('requests.Session.send') as send_mock:
            expected_response = MagicMock()
            expected_response.json.return_value = [
                {"upload_token": upload_token, "job": job_nr}]
            send_mock.side_effect = [
                ConnectionError,
                ConnectionError,
                expected_response]

            assert client.new_job(
                'LOAD-204',
                'fomars',
                'tank',
                'target.host',
                1234) == (
                job_nr,
                upload_token)

    def test_new_job_retry_api(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/')
        with patch('requests.Session.send') as send_mock:
            bad_response = MagicMock()
            bad_response.status_code = 500
            good_response = MagicMock()
            good_response.json.return_value = [
                {"upload_token": upload_token, "job": job_nr}]
            send_mock.side_effect = [bad_response, good_response]

            assert client.new_job(
                'LOAD-204',
                'fomars',
                'tank',
                'target.host',
                1234) == (
                job_nr,
                upload_token)

    def test_new_job_unavailable(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/',
            api_attempts=3,
            api_timeout=1)
        with patch('requests.Session.send') as send_mock:
            bad_response = MagicMock()
            bad_response.status_code = 500
            good_response = MagicMock()
            good_response.json.return_value = [
                {"upload_token": upload_token, "job": job_nr}]
            send_mock.side_effect = [
                bad_response,
                bad_response,
                bad_response,
                good_response]

            with pytest.raises(APIClient.JobNotCreated):
                client.new_job(
                    'LOAD-204',
                    'fomars',
                    'tank',
                    'target.host',
                    1234)

    def test_push_data(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/')
        with patch('requests.Session.send') as send_mock:
            mock_response = MagicMock()
            mock_response.json.return_value = [{"success": 1}]
            send_mock.return_value = mock_response

            assert client.push_test_data(
                job_nr, self.TEST_DATA, self.TEST_STATS) == 1

    def test_push_data_retry_network(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/')
        with patch('requests.Session.send') as send_mock:
            expected_response = MagicMock()
            expected_response.json.return_value = [{"success": 1}]
            send_mock.side_effect = [
                ConnectionError,
                ConnectionError,
                expected_response]

            result = client.push_test_data(
                job_nr, self.TEST_DATA, self.TEST_STATS)
            send_mock.assert_called()
            assert result == 1

    def test_push_data_retry_api(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/')
        with patch('requests.Session.send') as send_mock:
            bad_response = MagicMock()
            bad_response.status_code = 500
            good_response = MagicMock()
            good_response.json.return_value = [{"success": 1}]
            send_mock.side_effect = [bad_response, good_response]

            result = client.push_test_data(
                job_nr, self.TEST_DATA, self.TEST_STATS)
            send_mock.assert_called()
            assert result == 1

    def test_push_data_api_exception(self, job_nr, upload_token):
        client = APIClient(
            base_url='https://lunapark.test.yandex-team.ru/',
            api_timeout=1,
            api_attempts=3)
        with patch('requests.Session.send') as send_mock:
            bad_response = MagicMock()
            bad_response.status_code = 500
            good_response = MagicMock()
            good_response.json.return_value = [{"success": 1}]
            send_mock.side_effect = [
                bad_response,
                bad_response,
                bad_response,
                good_response]

            assert client.push_test_data(
                job_nr, self.TEST_DATA, self.TEST_STATS) == 0
