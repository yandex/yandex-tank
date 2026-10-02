"""MachineReport: report.json and hist.v1.jsonl.gz of the shooting for machines (schemas in schema/).

The plugin never changes the outcome of the shooting: every hook catches Exception, post_process returns the retcode
it got. When a correct report cannot be built, there are no files and the reason is in the log.
"""

import datetime
import json
import logging
import os
import socket
import time
from collections import defaultdict

from ...common.interfaces import AbstractPlugin, AggregateResultListener, DummyCollector, MonitoringDataListener
from ...version import VERSION as TANK_VERSION
from . import report

logger = logging.getLogger(__name__)

CGROUP_ROOT = '/sys/fs/cgroup'
PROC_CGROUP = '/proc/self/cgroup'
# the tank Solomon plugin is built only outside the open source tank, so it is recognized by its module
SOLOMON_MODULE = 'yandextank.plugins.Solomon.plugin'
# the bfg2020 tank plugin is not open source either; it shares the bfg section with the open source Bfg
BFG2020_MODULE = 'yandextank.plugins.Bfg2020.plugin'
YC_MODULE = 'yandextank.plugins.YCMonitoring.plugin'
SATURATION = {
    'cpu_util_pct': 90,
    'cpu_throttled_periods_pct': 5,
    'discarded_shots_pct': 1,
    'plan_deficit_pct': 5,
    'sustain_s': 60,
}


class Plugin(AbstractPlugin, AggregateResultListener, MonitoringDataListener):
    SECTION = 'machine_report'

    def __init__(self, core, cfg, name):
        super(Plugin, self).__init__(core, cfg, name)
        self._pools = None
        self._gun_type = None
        self._gun_version = None
        self._address = None
        self._started = None
        self._hist = None
        self._seconds = []
        self._no_report = None
        self._done = False
        self._sources = []
        # chunk key -> data metric names kept from it; {ts: {name: value}} by chunk key
        self._wanted = {}
        self._points = defaultdict(dict)
        self._cgroup = None
        self._cpu_source = 'unavailable'
        self._snapshots = []
        # snapshots are stamped by the monotonic clock shifted to epoch seconds: a jump of the wall clock would
        # turn the CPU of an interval into thousands of cores
        self._epoch = time.time() - time.monotonic()

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
        # before the shooting: hashing ammo files, reading an stpd and running pandora -version must not share its CPU
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
        """Phantom and bfg run the stepper in their configure, which the core calls for every plugin before any
        prepare_test: their profile is always ready here."""
        generator = self.core.job.generator_plugin
        kind = getattr(generator, 'SECTION', None)
        if kind == 'jmeter':
            raise report.NoReport('a jmeter jmx plan is not expressible as a load profile')
        if kind == 'pandora':
            if generator.config_contents is None:
                return  # the generator is prepared after this section: start_test reads the profile
            pools = report.pandora_pools(generator.config_contents['pools'], self.get_option('pools'))
            targets = [p.get('gun', {}).get('target') for p in generator.config_contents['pools']]
            address = next((str(t) for t in targets if t), None)
        elif kind == 'phantom':
            streams = generator.phantom.streams  # the main section, then multi in config order
            sources = [(s.stepper_wrapper, kind, s.tank_type == 'http', bool(s.ssl)) for s in streams]
            host = streams[0].address
            address = ('[{}]:{}' if ':' in host else '{}:{}').format(host, streams[0].port)
        elif kind == 'bfg':
            base = str((generator.get_option('gun_config') or {}).get('base_address') or '')
            http = generator.get_option('gun_type') == 'http'
            # the green worker runs green_threads_per_instance shots at once in each of its instances processes;
            # bfg2020 starts only processes and does not read worker_type
            green = generator.get_option('worker_type', '') == 'green' and type(generator).__module__ != BFG2020_MODULE
            threads = int(generator.get_option('green_threads_per_instance', 1000)) if green else 1
            sources = [(generator.stepper_wrapper, kind, http, base.startswith('https'), threads)]
            address = generator.get_option('address') or base or None
        else:
            raise report.NoReport('generator {} is not supported by plugin {}'.format(kind, report.PLUGIN_VERSION))
        if kind != 'pandora':
            pools = report.stepper_pools(sources, self.get_option('pools'), self.core.resource_manager)
        # all phantom streams write one phout, the aggregator reads it as one source
        report.check_pauses(pools, self.core.get_option('core', 'aggregator_max_wait', 31), shared=kind != 'pandora')
        for i, pool in enumerate(pools):
            if pool.grpc_by_default:
                logger.warning(
                    'MachineReport: pool %s shoots HTTP/2 without TLS and is taken for gRPC over h2c (errors behind '
                    'HTTP 200 are not seen); set machine_report.pools[%s].target_protocol: http for plain HTTP/2',
                    i,
                    i,
                )
        self._pools, self._gun_type, self._address = pools, kind, address
        self._gun_version = report.pandora_version(generator.pandora_cmd) if kind == 'pandora' else None

    def _open(self):
        self._started = time.monotonic()
        if self._pools is None:
            self._read_profile()
        if self._pools is None:
            raise report.NoReport('the generator has no config at the start of the shooting')
        self._sources = self._monitoring_specs()
        for s in self._sources:
            self._wanted.setdefault(s['host'], set()).update(
                report.data_name(s['kind'], m['name']) for m in s['metrics']
            )
        self._cgroup, why = report.find_cgroup(CGROUP_ROOT, PROC_CGROUP, os.getpid())
        if self._cgroup and report.cgroup_cpu(self._cgroup):
            self._cpu_source = self._cgroup.source
        logger.info(
            'MachineReport: generator CPU from %s (%s), %s: %s',
            self._cpu_source,
            why or self._cgroup,
            PROC_CGROUP,
            '; '.join((report._read(PROC_CGROUP) or '').split()),
        )
        self._sample()
        self._hist = report.HistWriter(os.path.join(self.core.artifacts_dir, report.HIST_FILE + '.part'))

    def _monitoring_specs(self):
        """Sources of the section with defaults; the metrics of the target CPU are read from its source."""
        cpu = (self.cfg.get('target') or {}).get('cpu') or {}
        specs = []
        for s in self.cfg.get('monitoring') or []:
            spec = {
                'id': s.get('id') or '{}:{}'.format(s['kind'], s['host']),
                'kind': s['kind'],
                'entity': s.get('entity') or 'target',
                'host': s['host'],
                'required': bool(s.get('required')),
                'metrics': [{'name': m['name'], 'unit': m['unit']} for m in s.get('metrics') or []],
            }
            if spec['id'] == cpu.get('source_id'):
                names = {m['name'] for m in spec['metrics']}
                for name in (cpu.get('usage_metric'), cpu.get('throttled_metric')):
                    if name and name not in names:
                        spec['metrics'].append({'name': name, 'unit': 'cores'})
            specs.append(spec)
        return specs

    def _sample(self):
        """A snapshot of the cgroup CPU counters, at least a second after the previous one: the plugin has no thread
        of its own, it samples on the callbacks of the core and the aggregator."""
        if self._cpu_source == 'unavailable':
            return
        try:
            now = self._epoch + time.monotonic()
            if self._snapshots and now - self._snapshots[-1][0] < 1:
                return
            read = report.cgroup_cpu(self._cgroup)
            if read:
                self._snapshots.append((now,) + read)
        except Exception:
            logger.debug('MachineReport: cannot read the cgroup CPU', exc_info=True)

    def is_test_finished(self):
        if self._hist is not None:
            self._sample()
        return -1

    def monitoring_data(self, data):
        """Keeps the points of the section sources; a later point of the same chunk key, ts and metric wins. A chunk
        the panel could not format comes as None: it is skipped, not the chunks after it."""
        if not self._wanted or self._hist is None:
            return
        for chunk in data or []:
            try:
                for key, block in chunk['data'].items():
                    names = self._wanted.get(key)
                    if names is None:
                        continue
                    row = self._points[key].setdefault(chunk['timestamp'], {})
                    row.update((name, value) for name, value in block['metrics'].items() if name in names)
            except Exception:
                logger.warning('MachineReport: a monitoring chunk in an unexpected format: %.200r', chunk)

    def on_aggregated_data(self, data, stats):
        if self._hist is None or self._no_report:
            return
        try:
            self._sample()
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
            'statuses': {'shooting': self._shooting(retcode)},
            'gun': {'type': self._gun_type, 'version': self._gun_version},
            'elapsed_s': time.monotonic() - self._started,
            'autostop_criteria': self._autostop_criteria(),
            'histograms': histograms,
            'monitoring': [dict(s, **self._config_status(s)) for s in self._sources],
            'points': self._points,
            'tolerance_s': section.get('monitoring_tolerance_s', 60),
            'generator': {
                'host': socket.gethostname() or 'unknown',
                'dc': dc,
                'cpu_model': report.cpu_model(),
                'cores': len(os.sched_getaffinity(0)),
                'cpu_limit_cores': self._cgroup.limit if self._cgroup else None,
            },
            'cpu': {'source': self._cpu_source, 'snapshots': self._snapshots},
            'saturation': dict(SATURATION, **(section.get('saturation') or {})),
            'target': self._target(section.get('target') or {}),
            'target_cpu': self._target_cpu((section.get('target') or {}).get('cpu')),
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
        address = section.get('address') or self._address or 'unknown'
        hosts = [
            {
                'host': h['host'],
                'dc': h.get('dc'),
                'cpu_model': h.get('cpu_model'),
                'cpu_model_source': h.get('cpu_model_source') or ('config' if h.get('cpu_model') else 'unknown'),
            }
            for h in section.get('hosts') or []
        ]
        return {'address': address, 'hosts': hosts}

    def _plugins(self, module):
        return [p for p in self.core.plugins.values() if type(p).__module__ == module]

    def _panels(self, source):
        """(Solomon plugin, panel) pairs of a solomon or monium source."""
        found = [(p, (p.get_option('panels') or {}).get(source['host'])) for p in self._plugins(SOLOMON_MODULE)]
        return [(p, panel) for p, panel in found if panel is not None]

    def _config_status(self, source):
        """Status of a source decided by the config: the Solomon panel is missing or is in several Solomon plugins,
        the monitoring plugin has no token (it silently keeps DummyCollector, nothing in the log), a sensor may
        return several series, or a metric of the section is no series of the panel."""
        if source['kind'] == 'yc_monitoring':
            plugins = self._plugins(YC_MODULE)
            if plugins and all(isinstance(p.collector, DummyCollector) for p in plugins):
                return {'status': 'error', 'reason': 'no token: the YCMonitoring plugin read nothing'}
            return {}
        if source['kind'] not in report.SOLOMON_KINDS:
            return {}
        found = self._panels(source)
        if not found:
            reason = 'the tank config has no Solomon panel {}'.format(source['host'])
            return {'status': 'error' if source['required'] else 'not_requested', 'reason': reason}
        if len(found) > 1:
            return {
                'status': 'error',
                'reason': 'ambiguous: Solomon panel {} is in several plugins'.format(source['host']),
            }
        plugin, panel = found[0]
        if isinstance(plugin.collector, DummyCollector):
            return {'status': 'error', 'reason': 'no token: the Solomon plugin read nothing'}
        problem = report.solomon_problem(panel.get('sensors'), [m['name'] for m in source['metrics']])
        return {'status': problem[0], 'reason': problem[1]} if problem else {}

    def _target_cpu(self, cpu):
        """target.cpu of the section, None when its metric cannot be the CPU of the whole target in cores."""
        if not cpu:
            return None
        source = next((s for s in self._sources if s['id'] == cpu['source_id']), None)
        if source is None:
            problem = 'no monitoring source {}'.format(cpu['source_id'])
        else:
            unit = next(m['unit'] for m in source['metrics'] if m['name'] == cpu['usage_metric'])
            panels = self._panels(source) if source['kind'] in report.SOLOMON_KINDS else []
            sensor = report.solomon_sensor(panels[0][1].get('sensors') or [], cpu['usage_metric']) if panels else None
            query = sensor.get('query') if isinstance(sensor, dict) else None
            if unit != 'cores':
                problem = 'metric {} is in {}, not in cores'.format(cpu['usage_metric'], unit)
            elif isinstance(query, str) and report.aggregation(query) not in (None, 'sum'):
                problem = 'Solomon query {} does not sum the series of the target'.format(query)
            else:
                return cpu
        logger.warning('MachineReport: no target CPU: %s', problem)
        return None

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
