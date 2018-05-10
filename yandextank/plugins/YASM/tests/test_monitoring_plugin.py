import pytest

from yandextank.plugins.YASM.plugin import map_metric_name


@pytest.mark.skip()
@pytest.mark.parametrize('init_name, expected_name', [
    ('portoinst-cpu_usage_cores_tmmv', 'custom:portoinst-cpu_usage_cores_tmmv'),
    ('portoinst-cpu_guarantee_cores_tmmv', 'custom:portoinst-cpu_guarantee_cores_tmmv'),
    ('portoinst-cpu_limit_cores_tmmv', 'custom:portoinst-cpu_limit_cores_tmmv'),
    ('portoinst-cpu_wait_cores_tmmv', 'custom:portoinst-cpu_wait_cores_tmmv'),
    ('portoinst-memory_usage_gb_tmmv', 'custom:portoinst-memory_usage_gb_tmmv'),
    ('portoinst-memory_limit_gb_tmmv', 'custom:portoinst-memory_limit_gb_tmmv'),
    ('portoinst-io_read_fs_bytes_tmmv', 'custom:portoinst-io_read_fs_bytes_tmmv'),
    ('portoinst-io_write_fs_bytes_tmmv', 'custom:portoinst-io_write_fs_bytes_tmmv'),
    ('portoinst-io_limit_bytes_tmmv', 'custom:portoinst-io_limit_bytes_tmmv'),
    ('conv(unistat-auto_disk_rootfs_usage_bytes_axxx, Gi)', 'custom:unistat-auto_disk_rootfs_usage_bytes_axxx'),
    ('conv(unistat-auto_disk_rootfs_total_bytes_axxx, Gi)', 'custom:unistat-auto_disk_rootfs_total_bytes_axxx'),
    ('portoinst-net_mb_summ', 'custom:portoinst-net_mb_summ'),
    ('portoinst-net_guarantee_mb_summ', 'custom:portoinst-net_guarantee_mb_summ'),
    ('portoinst-net_limit_mb_summ', 'custom:portoinst-net_limit_mb_summ')]
)
def test_name_mapper(init_name, expected_name):
    assert map_metric_name(init_name) == expected_name
