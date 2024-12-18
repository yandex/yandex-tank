import os
import json

try:
    import pathlib
except ImportError:
    import pathlib2 as pathlib
import numpy as np
import pandas as pd
import time
import logging
import pytest
from yandextank.contrib.netort.netort.data_manager import DataSession

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)


@pytest.fixture()
def empty_data_frame():
    return pd.DataFrame(columns=['ts', 'value'])


@pytest.fixture()
def trivial_data_frame():
    return pd.DataFrame([[0, 0]], columns=['ts', 'value'])


@pytest.fixture()
def sin_data_frame():
    SIZE = 100

    X = (np.arange(SIZE) * 1e4).astype(int)

    df = pd.DataFrame()
    df['ts'] = X
    Xdot = X * 1e-6
    df['value'] = np.sin(Xdot)
    return df


@pytest.fixture()
def event_data_frame():
    SIZE = 200

    np.random.seed(42)

    X = (np.arange(SIZE) * 1e4).astype(int)
    df = pd.DataFrame()
    df['ts'] = X
    df['value'] = np.random.choice("a quick brown fox jumped over the lazy dog".split(), len(X))
    return df


@pytest.fixture()
def data_session(tmp_path):
    artifacts_base_dir = tmp_path / "logs"
    config = {
        'clients': [
            {
                'type': 'local_storage',
            }
        ],
        'test_start': int(time.time() * 1e6),
    }
    data_session = DataSession(config=config, artifacts_dir=str(artifacts_base_dir))
    return data_session


@pytest.mark.xfail
def test_dir_created(tmp_path):
    artifacts_base_dir = tmp_path / "logs"
    config = {
        'clients': [
            {
                'type': 'local_storage',
            }
        ],
        'test_start': int(time.time() * 1e6),
    }
    data_session = DataSession(config=config, artifacts_dir=str(artifacts_base_dir))
    # TODO: make this pass. Datasession dir and meta.json should be created as soon as possible
    # assert os.path.isdir(artifacts_base_dir), "Artifacts base dir should exist after datasession have been created"
    # assert os.path.isdir(data_session.artifacts_dir), "Artifacts dir should exist after datasession have been created"
    data_session.close()
    assert os.path.isdir(artifacts_base_dir), "Artifacts base dir should exist after datasession have ended"
    assert os.path.isdir(data_session.artifacts_dir), "Artifacts dir should exist after datasession have ended"
    assert os.path.isfile(
        pathlib.Path(data_session.artifacts_dir) / 'meta.json'
    ), "Metadata file should have been created"

    with open(pathlib.Path(data_session.artifacts_dir) / 'meta.json') as meta_file:
        meta = json.load(meta_file)

    assert 'job_meta' in meta, "Metadata should have been written to meta.json"


@pytest.mark.xfail
def test_raw_metric(sin_data_frame, data_session):
    metric = data_session.new_true_metric(
        "My Raw Metric", raw=True, aggregate=False, hostname='localhost', source='PyTest', group='None'
    )
    metric.put(sin_data_frame)
    # TODO: make this pass. Metric should be created as soon as possible after it was created
    # assert os.path.isdir(metric_path), "Artifacts base dir should exist after datasession have been created"
    data_session.close()
    with open(pathlib.Path(data_session.artifacts_dir) / 'meta.json') as meta_file:
        meta = json.load(meta_file)

    assert 'metrics' in meta, "Metrics should have been written to meta.json"
    assert len(meta['metrics']) == 1, "Exactly one metric should have been written to meta.json"

    metric_id = list(meta['metrics'])[0]
    metric_data_path = pathlib.Path(data_session.artifacts_dir) / '{metric_id}.data'.format(metric_id=metric_id)
    assert os.path.isfile(metric_data_path), "Metric data should have been written"

    with open(metric_data_path) as data_file:
        metric_data = data_file.readlines()

    assert len(metric_data) == 1 + 100, "There should be one header line and exactly 100 data lines in the data file"

    metric_meta = json.loads(metric_data[0])
    assert "type" in metric_meta, "Type info should be in the header"
    assert metric_meta["type"] == "TypeTimeSeries", "Type of metric should be TypeTimeSeries"

    fields = metric_data[1].strip().split("\t")
    assert len(fields) == 2, "There should be exactly two tab-separated fields in data"
    assert fields[0] == "0", "The timestamp field should be equal to 0"
    assert fields[1] == "0.0", "The value field should be equal to 0.0"


@pytest.mark.xfail
def test_quantiles_metric(sin_data_frame, data_session):
    metric = data_session.new_true_metric(
        "My Aggregated Metric", raw=False, aggregate=True, hostname='localhost', source='PyTest', group='None'
    )
    metric.put(sin_data_frame)

    # TODO: make this line unnecessary
    # data will stuck in internal buffers without this line
    # MAGIC VALUE of 12*1e6 chosen empirically. Some asserts below depend on it in some magical way
    metric.put(pd.DataFrame([[12 * 1e6, 0]], columns=['ts', 'value']))

    # TODO: make this pass. Metric should be created as soon as possible after it was created
    # assert os.path.isdir(metric_path), "Artifacts base dir should exist after datasession have been created"

    # TODO: make this line unnecessary
    # if no time.sleep, no distribution data will be written
    time.sleep(1)

    data_session.close()
    with open(pathlib.Path(data_session.artifacts_dir) / 'meta.json') as meta_file:
        meta = json.load(meta_file)

    assert 'metrics' in meta, "Metrics should have been written to meta.json"
    assert (
        len(meta['metrics']) == 2
    ), "Exactly two metrics should have been written to meta.json (aggregates and distibutions)"

    metric_types = set(m['type'] for m in meta['metrics'].values())
    assert metric_types == {'TypeQuantiles', 'TypeDistribution'}, "Metric types should be Quantiles and Distribution"

    metric_ids = {v['type']: k for k, v in meta['metrics'].items()}

    q_metric_id = metric_ids['TypeQuantiles']
    q_metric_data_path = pathlib.Path(data_session.artifacts_dir) / '{q_metric_id}.data'.format(q_metric_id=q_metric_id)
    assert os.path.isfile(q_metric_data_path), "Quantile data should have been written"

    with open(q_metric_data_path) as data_file:
        q_metric_data = data_file.readlines()

    # this test depends on MAGIC VALUE above and flacky even with constant timestamp
    assert len(q_metric_data) == 2, "There should be a header and exactly one data line in the data file"

    q_metric_meta = json.loads(q_metric_data[0])
    assert "type" in q_metric_meta, "Type info should be in the header"
    assert q_metric_meta["type"] == "TypeQuantiles", "Type of quantile data should be TypeQuantiles"

    fields = q_metric_data[1].strip().split("\t")
    assert len(fields) == 15, "There should be exactly 15 tab-separated fields in quantile data"
    assert fields[0] == "0", "The timestamp field should be equal to 0"
    assert fields[1] == "0.0", "The q0 field should be equal to 0.0"

    d_metric_id = metric_ids['TypeDistribution']
    d_metric_data_path = pathlib.Path(data_session.artifacts_dir) / '{d_metric_id}.data'.format(d_metric_id=d_metric_id)
    assert os.path.isfile(d_metric_data_path), "Distribution data should have been written"

    with open(d_metric_data_path) as data_file:
        d_metric_data = data_file.readlines()

    # this test depends on MAGIC VALUE above and flacky even with constant timestamp
    assert len(d_metric_data) == 2, "There should be a header and exactly one data line in the data file"

    d_metric_meta = json.loads(d_metric_data[0])
    assert "type" in d_metric_meta, "Type info should be in the header"
    assert d_metric_meta["type"] == "TypeDistribution", "Type of distribution data should be TypeDistribution"

    fields = d_metric_data[1].strip().split("\t")
    assert len(fields) == 4, "There should be exactly 4 tab-separated fields in distribution data"
    assert fields[0] == "0", "The timestamp field should be equal to 0"
    assert fields[1] == "0" and fields[2] == "10" and fields[3] == "100", "Value fields should be 0, 10 and 100"


@pytest.mark.xfail
def test_raw_events(data_session, event_data_frame):
    metric = data_session.new_event_metric(
        "My Event Metric", raw=True, aggregate=False, hostname='localhost', source='PyTest', group='None'
    )
    metric.put(event_data_frame)
    # TODO: make this pass. Metric should be created as soon as possible after it was created
    # assert os.path.isdir(metric_path), "Artifacts base dir should exist after datasession have been created"
    data_session.close()
    with open(pathlib.Path(data_session.artifacts_dir) / 'meta.json') as meta_file:
        meta = json.load(meta_file)

    assert 'metrics' in meta, "Events stream should have been written to meta.json"
    assert len(meta['metrics']) == 1, "Exactly one events stream should have been written to meta.json"

    metric_id = list(meta['metrics'])[0]
    metric_data_path = pathlib.Path(data_session.artifacts_dir) / '{metric_id}.data'.format(metric_id=metric_id)
    assert os.path.isfile(metric_data_path), "Metric data should have been written"

    with open(metric_data_path) as data_file:
        metric_data = data_file.readlines()

    assert len(metric_data) == 1 + 100, "There should be one header line and exactly 100 data lines in the data file"

    metric_meta = json.loads(metric_data[0])
    assert "type" in metric_meta, "Type info should be in the header"
    assert metric_meta["type"] == "TypeEvents", "Type of events stream should be TypeEvents"

    fields = metric_data[1].strip().split("\t")
    assert len(fields) == 2, "There should be exactly two tab-separated fields in data"
    assert fields[0] == "0", "The timestamp field should be equal to 0"
    assert fields[1] == "the", "The value field should be equal to 'the'"


@pytest.mark.xfail
def test_aggregated_events(data_session, event_data_frame):
    metric = data_session.new_event_metric(
        "My Event Metric", raw=False, aggregate=True, hostname='localhost', source='PyTest', group='None'
    )
    metric.put(event_data_frame)
    # TODO: get rid of following line with MAGIC VALUE:
    metric.put(pd.DataFrame([[12 * 1e6, 'fox']], columns=['ts', 'value']))
    # TODO: make this pass. Metric should be created as soon as possible after it was created
    # assert os.path.isdir(metric_path), "Artifacts base dir should exist after datasession have been created"
    time.sleep(1)
    data_session.close()
    with open(pathlib.Path(data_session.artifacts_dir) / 'meta.json') as meta_file:
        meta = json.load(meta_file)

    assert 'metrics' in meta, "Events stream should have been written to meta.json"
    assert len(meta['metrics']) == 1, "Exactly one events stream should have been written to meta.json"

    metric_id = list(meta['metrics'])[0]
    metric_data_path = pathlib.Path(data_session.artifacts_dir) / '{metric_id}.data'.format(metric_id=metric_id)
    assert os.path.isfile(metric_data_path), "Metric data should have been written"

    with open(metric_data_path) as data_file:
        metric_data = data_file.readlines()

    assert len(metric_data) == 1 + 18, "There should be one header line and exactly 18 data lines in the data file"

    metric_meta = json.loads(metric_data[0])
    assert "type" in metric_meta, "Type info should be in the header"
    assert metric_meta["type"] == "TypeHistogram", "Type of events stream should be TypeHistogram"

    fields = metric_data[1].strip().split("\t")
    assert len(fields) == 3, "There should be exactly two tab-separated fields in data"
    assert fields[0] == "0", "The timestamp field should be equal to 0"
    assert fields[1] == "a", "The category field should be equal to 'a'"
    assert fields[2] == "9", "The value field should be equal to 9"
