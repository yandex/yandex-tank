import logging

import pytest
import requests
from mock import MagicMock, patch

from yandextank.plugins.Pandora.reader import PandoraStatsPoller, PandoraStatsReader


def make_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    return response


@pytest.mark.parametrize(
    'payload, expected_instances',
    [
        ({'engine_ReqPS': 42, 'engine_LastMaxActiveRequests': 7}, 7),
        ({'engine_ReqPS': 42, 'engine_ActiveRequests': 5}, 5),
        ({'engine_ReqPS': 42}, 0),
    ],
)
def test_poll_reads_expvar_metrics(payload, expected_instances):
    response = make_response(payload)
    poller = PandoraStatsPoller(1234)

    with patch('yandextank.plugins.Pandora.reader.requests.get', return_value=response) as request:
        result = poller._poll(100)

    request.assert_called_once_with('http://localhost:1234/debug/vars', timeout=0.9)
    response.raise_for_status.assert_called_once_with()
    assert result == {'ts': 100, 'metrics': {'instances': expected_instances, 'reqps': 42}}


@pytest.mark.parametrize(
    'request_error',
    [
        requests.ConnectionError('connection refused'),
        requests.Timeout('timeout'),
    ],
)
def test_poll_uses_zero_fallback_for_request_errors(request_error, caplog):
    poller = PandoraStatsPoller(1234)

    with patch('yandextank.plugins.Pandora.reader.requests.get', side_effect=request_error):
        with caplog.at_level(logging.WARNING):
            result = poller._poll(100)

    assert result == {'ts': 100, 'metrics': {'instances': 0, 'reqps': 0}}
    assert 'sent RPS is unavailable' in caplog.text
    assert 'zero fallback' in caplog.text


def test_poll_uses_zero_fallback_for_http_error():
    response = make_response({'engine_ReqPS': 42})
    response.raise_for_status.side_effect = requests.HTTPError('server error')
    poller = PandoraStatsPoller(1234)

    with patch('yandextank.plugins.Pandora.reader.requests.get', return_value=response):
        result = poller._poll(100)

    response.json.assert_not_called()
    assert result == {'ts': 100, 'metrics': {'instances': 0, 'reqps': 0}}


def test_poll_uses_zero_fallback_for_invalid_json():
    response = make_response(None)
    response.json.side_effect = ValueError('invalid json')
    poller = PandoraStatsPoller(1234)

    with patch('yandextank.plugins.Pandora.reader.requests.get', return_value=response):
        result = poller._poll(100)

    assert result == {'ts': 100, 'metrics': {'instances': 0, 'reqps': 0}}


@pytest.mark.parametrize('payload', [{}, [], None])
def test_poll_uses_zero_fallback_for_invalid_expvar_payload(payload):
    poller = PandoraStatsPoller(1234)

    with patch('yandextank.plugins.Pandora.reader.requests.get', return_value=make_response(payload)):
        result = poller._poll(100)

    assert result == {'ts': 100, 'metrics': {'instances': 0, 'reqps': 0}}


def test_poll_warns_once_until_expvar_recovers(caplog):
    recovered = make_response({'engine_ReqPS': 12, 'engine_ActiveRequests': 3})
    poller = PandoraStatsPoller(1234)

    with patch(
        'yandextank.plugins.Pandora.reader.requests.get',
        side_effect=[requests.ConnectionError('first'), requests.ConnectionError('second'), recovered],
    ):
        with caplog.at_level(logging.INFO):
            poller._poll(100)
            poller._poll(101)
            result = poller._poll(102)

    pandora_logs = [record for record in caplog.records if record.name == 'yandextank.plugins.Pandora.reader']
    warnings = [record for record in pandora_logs if record.levelno == logging.WARNING]
    recovery_messages = [record for record in pandora_logs if record.levelno == logging.INFO]
    assert len(warnings) == 1
    assert len(recovery_messages) == 1
    assert 'available again' in recovery_messages[0].message
    assert result == {'ts': 102, 'metrics': {'instances': 3, 'reqps': 12}}


def test_managed_reader_does_not_poll_default_port_before_endpoint():
    reader = PandoraStatsReader(True, None)
    try:
        with patch('yandextank.plugins.Pandora.reader.requests.get') as request:
            next(reader)
            assert not reader.poller._port_ready.wait(0.05)
            request.assert_not_called()
            reader.set_port(4321)
            assert reader.poller._port_ready.wait(0.1)
    finally:
        reader.close()


def test_managed_reader_can_use_zero_fallback_without_polling_foreign_port():
    reader = PandoraStatsReader(True, None)
    try:
        with patch('yandextank.plugins.Pandora.reader.requests.get') as request:
            next(reader)
            reader.disable_expvar()
            assert next(reader)[0]['metrics'] == {'instances': 0, 'reqps': 0}
            request.assert_not_called()
    finally:
        reader.close()
