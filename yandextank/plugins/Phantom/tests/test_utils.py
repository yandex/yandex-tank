import pytest

from yandextank.plugins.Phantom import utils


@pytest.fixture
def host_cpus(monkeypatch):
    """Host with 256 cores: the old default was min(256 / 2 + 1, 128) = 128."""
    monkeypatch.setattr(utils.multiprocessing, 'cpu_count', lambda: 256)


def test_threads_from_cgroup_v2(tmp_path, host_cpus):
    (tmp_path / 'cpu.max').write_text('660500 100000\n')
    assert utils.default_threads(str(tmp_path)) == 7


def test_threads_from_cgroup_v1(tmp_path, host_cpus):
    (tmp_path / 'cpu').mkdir()
    (tmp_path / 'cpu' / 'cpu.cfs_quota_us').write_text('660500\n')
    (tmp_path / 'cpu' / 'cpu.cfs_period_us').write_text('100000\n')
    assert utils.default_threads(str(tmp_path)) == 7


def test_threads_fallback_without_limit(tmp_path, host_cpus):
    (tmp_path / 'cpu.max').write_text('max 100000\n')
    (tmp_path / 'cpu').mkdir()
    (tmp_path / 'cpu' / 'cpu.cfs_quota_us').write_text('-1\n')
    (tmp_path / 'cpu' / 'cpu.cfs_period_us').write_text('100000\n')
    assert utils.default_threads(str(tmp_path)) == 128


def test_threads_fallback_without_cgroup_files(tmp_path, host_cpus):
    assert utils.default_threads(str(tmp_path / 'nowhere')) == 128
