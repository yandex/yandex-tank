"""MachineReport: report.json and hist.v1.jsonl.gz of the shooting for machines (schemas in schema/).

The plugin never changes the outcome of the shooting: every hook catches Exception, post_process returns the retcode
it got. When a correct report cannot be built, there are no files and the reason is in the log.
"""

import datetime
import json
import logging
import os
import socket

from ...common.interfaces import AbstractPlugin, AggregateResultListener
from ...version import VERSION as TANK_VERSION
from ..Phantom.utils import _cgroup_cpu_limit
from . import report

logger = logging.getLogger(__name__)

CGROUP_ROOT = '/sys/fs/cgroup'
MONITORING_NOT_READ = 'the plugin version does not read monitoring yet'


class Plugin(AbstractPlugin, AggregateResultListener):
    SECTION = 'machine_report'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self._pools = None
        self._gun_version = None
        self._hist = None
        self._seconds = []
        self._no_report = None
        self._done = False

    @staticmethod
    def get_key():
        return __file__

    def get_available_options(self):
        return [
            'steady_trim_s',
            'monitoring_tolerance_s',
            'pools',
            'generator',
            'monitoring',
            'target',
            'saturation',
            'perforator',
        ]

    def configure(self):
        try:
            self.core.job.subscribe_plugin(self)
        except Exception:
            logger.exception('MachineReport: cannot subscribe to aggregated data, no report will be written')
            self._no_report = 'the plugin could not subscribe to aggregated data'

    def prepare_test(self):
        # before the shooting: hashing ammo files and running pandora -version must not share its CPU
        self._guarded(self._read_profile)

    def start_test(self):
        self._guarded(self._open)

    def _guarded(self, step):
        if self._no_report:
            return
        try:
            step()
        except report.NoReport as e:
            self._no_report = str(e)
            logger.warning('MachineReport: no report will be written: %s', e)
        except Exception as e:
            self._no_report = 'failed to read the load profile: {}'.format(e)
            logger.exception('MachineReport: failed to read the load profile, no report will be written')

    def _read_profile(self):
        generator = self.core.job.generator_plugin
        kind = getattr(generator, 'SECTION', None)
        if kind == 'jmeter':
            raise report.NoReport('a jmeter jmx plan is not expressible as a load profile')
        if kind != 'pandora':
            raise report.NoReport('generator {} is not supported by plugin {}'.format(kind, report.PLUGIN_VERSION))
        if generator.config_contents is None:
            return  # the generator is prepared after this section: start_test reads the profile
        pools = report.pandora_pools(generator.config_contents['pools'], self.get_option('pools'))
        report.check_pauses(pools, self.core.get_option('core', 'aggregator_max_wait', 31))
        for i, pool in enumerate(pools):
            if pool.grpc_by_default:
                logger.warning(
                    'MachineReport: pool %s shoots HTTP/2 without TLS and is taken for gRPC over h2c (errors behind '
                    'HTTP 200 are not seen); set machine_report.pools[%s].target_protocol: http for plain HTTP/2',
                    i,
                    i,
                )
        self._pools = pools
        self._gun_version = report.pandora_version(generator.pandora_cmd)

    def _open(self):
        if self._pools is None:
            self._read_profile()
        if self._pools is None:
            raise report.NoReport('the generator has no config at the start of the shooting')
        log_cgroup('start')
        self._hist = report.HistWriter(os.path.join(self.core.artifacts_dir, report.HIST_FILE + '.part'))

    def on_aggregated_data(self, data, stats):
        if self._hist is None or self._no_report:
            return
        try:
            summary, lines = report.summarize_second(data, stats)
            self._hist.write(lines)
            # ~1 MB per hour per case; merge seconds by ts on arrival if day-long runs with many cases matter
            self._seconds.append(summary)
        except Exception as e:
            self._no_report = 'aggregated data lost: {}'.format(e)
            logger.exception('MachineReport: aggregated data lost, no report will be written')

    def post_process(self, retcode):
        if self._done:
            return retcode
        self._done = True
        published = False
        try:
            self._publish(retcode)
            published = True
        except report.NoReport as e:
            logger.warning('MachineReport: no report: %s', e)
        except Exception:
            logger.exception('MachineReport: failed to write the report')
        finally:
            try:
                self._cleanup(published)
            except Exception:
                logger.exception('MachineReport: cleanup failed')
        return retcode

    def _paths(self):
        directory = self.core.artifacts_dir
        return os.path.join(directory, report.HIST_FILE), os.path.join(directory, report.REPORT_FILE)

    def _publish(self, retcode):
        if self._no_report:
            raise report.NoReport(self._no_report)
        if self._hist is None:
            raise report.NoReport('the shooting did not start')
        log_cgroup('end')
        histograms = self._hist.artifact()
        doc = report.build(self._seconds, report.read_hist(self._hist.path), self._context(retcode, histograms))
        text = json.dumps(doc, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        hist_path, report_path = self._paths()
        # hist first: report.json is the mark of a complete set
        os.replace(self._hist.path, hist_path)
        with open(report_path + '.part', 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(report_path + '.part', report_path)
        logger.info('MachineReport: %s and %s written', report_path, hist_path)

    def _cleanup(self, published):
        if self._hist is not None:
            try:
                self._hist.close()
            except Exception:
                logger.debug('MachineReport: closing histograms failed', exc_info=True)
        hist_path, report_path = self._paths()
        leftovers = [hist_path + '.part', report_path + '.part'] + ([] if published else [hist_path])
        for path in leftovers:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning('MachineReport: cannot remove %s', path, exc_info=True)

    def _context(self, retcode, histograms):
        config = self.core.config.validated
        firestarter = (config.get('metaconf') or {}).get('firestarter') or {}
        labels = {str(k): str(v) for k, v in (firestarter.get('labels') or {}).items()}
        section = self.cfg
        sources = [
            {
                'id': s.get('id') or '{}:{}'.format(s['kind'], s['host']),
                'kind': s['kind'],
                'entity': s.get('entity') or 'target',
                'host': s['host'],
                'required': bool(s.get('required')),
                'status': 'unsupported',
                'reason': MONITORING_NOT_READ,
            }
            for s in section.get('monitoring') or []
        ]
        generator = section.get('generator') or {}
        dc = report.generator_dc(generator.get('dc'), generator.get('dc_env') or [], os.environ)
        requested_dc = firestarter.get('dc')
        if requested_dc and dc and requested_dc != dc:
            logger.warning('MachineReport: generator dc %s differs from metaconf.firestarter.dc %s', dc, requested_dc)
        return {
            'pools': self._pools,
            'trim_s': section.get('steady_trim_s', 15),
            'provenance': {
                'plugin_version': report.PLUGIN_VERSION,
                'tank_version': TANK_VERSION,
                'config_sha256': report.config_sha256(config),
                'labels': labels,
                'series': labels.get('series'),
                'test_id': None,
                'tank_job_id': str(self.core.test_id),
                'run_id': None,
                'created_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            },
            'statuses': {'shooting': self._shooting(retcode), 'completeness': report.completeness(sources)},
            'gun': {'type': 'pandora', 'version': self._gun_version},
            'autostop_criteria': self._autostop_criteria(),
            'histograms': histograms,
            'monitoring': sources,
            'generator': {
                'host': socket.gethostname() or 'unknown',
                'dc': dc,
                'cpu_model': report.cpu_model(),
                'cores': len(os.sched_getaffinity(0)),
                'cpu_limit_cores': _cgroup_cpu_limit(CGROUP_ROOT),
                'cpu': {'source': 'unavailable', 'windows': []},
                'saturation': {'status': 'unknown', 'signals': []},
            },
            'target': self._target(section.get('target') or {}),
            'perforator': self._perforator(section.get('perforator')),
        }

    def _autostop(self):
        return next((p for p in self.core.plugins.values() if getattr(p, 'SECTION', None) == 'autostop'), None)

    def _autostop_criteria(self):
        autostop = self._autostop()
        return [c for c in (autostop.get_option('autostop') or []) if c] if autostop else []

    def _shooting(self, retcode):
        autostop = self._autostop()
        cause = getattr(autostop, 'cause_criterion', None)
        if cause is not None:
            criterion = next((text for text, c in getattr(autostop, '_criterions', {}).items() if c is cause), None)
            return {'status': 'AUTOSTOPPED', 'retcode': retcode, 'autostop_criterion': criterion}
        if self.core.interrupted.is_set():
            status = 'STOPPED'
        else:
            status = 'DONE' if retcode == 0 else 'FAILED'
        return {'status': status, 'retcode': retcode, 'autostop_criterion': None}

    def _target(self, section):
        address = section.get('address')
        if not address:
            targets = [p.get('gun', {}).get('target') for p in self.core.job.generator_plugin.config_contents['pools']]
            address = next((str(t) for t in targets if t), 'unknown')
        hosts = [
            {
                'host': h['host'],
                'dc': h.get('dc'),
                'cpu_model': h.get('cpu_model'),
                'cpu_model_source': h.get('cpu_model_source') or ('config' if h.get('cpu_model') else 'unknown'),
            }
            for h in section.get('hosts') or []
        ]
        return {'address': address, 'hosts': hosts, 'cpu': None}

    @staticmethod
    def _perforator(section):
        if not section:
            return {'status': 'not_requested'}
        return {
            'status': 'pending',
            'selector': section['selector'],
            'microscope_window': section['microscope_window'],
            'microscope_id': section['microscope_id'],
            'process_comm': section['process_comm'],
        }


def log_cgroup(stage, root=CGROUP_ROOT):
    """Logs the cgroup the generator CPU is read from in the next plugin version: its version, paths, quota and
    throttling counters. Throttling between start and end shows whether the cgroup is the generator's own."""
    try:
        if os.path.exists(os.path.join(root, 'cgroup.controllers')):
            version, stat = 'v2', os.path.join(root, 'cpu.stat')
        else:
            version, stat = 'v1', os.path.join(root, 'cpu', 'cpu.stat')
        try:
            with open('/proc/self/cgroup') as f:
                paths = f.read().strip().replace('\n', '; ')
        except OSError:
            paths = None
        try:
            with open(stat) as f:
                counters = dict(line.split() for line in f if len(line.split()) == 2)
        except OSError:
            version, counters = None, {}
        logger.info(
            'MachineReport: cgroup at %s: version %s, paths %s, limit %s cores, %s',
            stage,
            version,
            paths,
            _cgroup_cpu_limit(root),
            {k: v for k, v in counters.items() if k.startswith(('nr_', 'throttled', 'usage'))},
        )
    except Exception:
        logger.debug('MachineReport: cannot read cgroup', exc_info=True)
