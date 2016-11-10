"""Known metrics decoder"""

import logging

logger = logging.getLogger(__name__)


class MetricsDecoder(object):
    def __init__(self):
        self.known_metrics = {
            'mem_used': 'Memory_used',
            'mem_free': 'Memory_free',
            'mem_buffered': 'Memory_buff',
            'mem_cached': 'Memory_cached',
            'net_packets_recv': 'Net_rx',
            'net_packets_sent': 'Net_tx',
            'net_bytes_recv': 'Net_recv',
            'net_bytes_sent': 'Net_send',
            'kernel_context_switches': 'System_csw',
            'kernel_interrupts': 'System_int',
            'kernel_processes_forked': 'System_forks',
            'processes_total': 'System_numproc',
            'processes_total_threads': 'System_numthreads',
            'system_load1': 'System_la1',
            'system_load5': 'System_la5',
            'system_load15': 'System_la15',
            'cpu_usage_user': 'CPU_user',
            'cpu_usage_system': 'CPU_system',
            'cpu_usage_idle': 'CPU_idle',
            'cpu_usage_iowait': 'CPU_iowait',
            'cpu_usage_irq': 'CPU_irq',
            'cpu_usage_nice': 'CPU_nice',
            'cpu_usage_softirq': 'CPU_softirq',
            'cpu_usage_steal': 'CPU_steal',
            'cpu_usage_guest': 'CPU_guest',
            'diskio_read_bytes': 'Disk_read',
            'diskio_write_bytes': 'Disk_write',
            'nstat_TcpRetransSegs': 'Net_retransmit'
        }

        self.diff_metrics = [self.find_common_names(key) for key in [
                'kernel_context_switches', 'kernel_interrupts',
                'diskio_read_bytes', 'diskio_write_bytes',
                'net_packets_recv', 'net_packets_sent', 'net_bytes_recv', 'net_bytes_sent',
                'diskio_io_time', 'diskio_read_time', 'diskio_reads', 'diskio_write_time', 'diskio_writes',
                'kernel_processes_forked',
                'nstat_TcpRetransSegs'
            ]
        ]

    def find_common_names(self, key):
        if key in self.known_metrics:
            return self.known_metrics[key]
        else:
            return 'custom:{}'. format(key)

decoder = MetricsDecoder()
