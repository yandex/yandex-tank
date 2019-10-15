
import pytest

from yandextank.validator.validator import TankConfig, ValidationError, PatchedValidator

CFG_VER_I_0 = {
    "version": "1.9.3",
    "core": {
        'operator': 'fomars',
        'artifacts_base_dir': './'
    },
    'telegraf': {
        'package': 'yandextank.plugins.Telegraf',
        'enabled': True,
        'config': 'monitoring.xml',
        'disguise_hostnames': True
    },
    'phantom': {
        'package': 'yandextank.plugins.Phantom',
        'enabled': True,
        'address': 'nodejs.load.yandex.net',
        'header_http': '1.1',
        'uris': ['/'],
        'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 10m)'}
    },
    'lunapark': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://lunapark.test.yandex-team.ru/'
    },
    'overload': {
        'package': 'yandextank.plugins.DataUploader',
        'enabled': True,
        'api_address': 'https://overload.yandex.net/',
        'token_file': 'token.txt'
    }
}

PHANTOM_SCHEMA_V_G = {
    'phantom_path': {
        'type': 'string',
        'default': 'phantom'
    },
    'buffered_seconds': {
        'type': 'integer',
        'default': 2
    },
    'address': {
        'type': 'string',
        'required': True
    },
    'header_http': {
        'type': 'string'
    },
    'uris': {
        'type': 'string'
    },
    'headers': {
        'type': 'string',
        'regex': r'(\[[\w\d\.]+:\s[\w\d\.]+\]\s*)+'
    },
    'rps_schedule': {
        'type': 'string'
    },
    'writelog': {
        'type': 'string'
    }
}


@pytest.mark.parametrize('config, expected', [
    ({
     "version": "1.9.3",
     "core": {
         'operator': 'fomars',
         'artifacts_base_dir': './',
         'ignore_lock': False
     },
     'telegraf': {
         'package': 'yandextank.plugins.Telegraf',
         'enabled': True,
         'config': 'monitoring.xml',
         'disguise_hostnames': True,
         'kill_old': True
     },
     'phantom': {
         'package': 'yandextank.plugins.Phantom',
         'enabled': True,
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
         'uris': ['/'],
         'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 10m)'}}
     },
     {
     "version": "1.9.3",
     "core": {
         'operator': 'fomars',
         'artifacts_base_dir': './',
         'lock_dir': '/var/lock/',
         'taskset_path': 'taskset',
         'affinity': '',
         'ignore_lock': False
     },
     'telegraf': {
         'package': 'yandextank.plugins.Telegraf',
         'enabled': True,
         'config': 'monitoring.xml',
         'disguise_hostnames': True,
         'default_target': 'localhost',
         'ssh_timeout': '5s',
         'kill_old': True
     },
     'phantom': {
         'package': 'yandextank.plugins.Phantom',
         'enabled': True,
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
         'uris': ['/'],
         'buffered_seconds': 2,
         'phantom_path': 'phantom',
         'affinity': '',
         'enum_ammo': False,
         'phout_file': '',
         'phantom_modules_path': '/usr/lib/phantom',
         'threads': None,
         'writelog': '0',
         'timeout': '11s',
         'additional_libs': [],
         'config': '',
         'gatling_ip': '',
         'instances': 1000,
         'method_options': '',
         'method_prefix': 'method_stream',
         'phantom_http_entity': '8M',
         'phantom_http_field': '8K',
         'phantom_http_field_num': 128,
         'phantom_http_line': '1K',
         'source_log_prefix': '',
         'ssl': False,
         'tank_type': 'http',
         'ammo_limit': -1,
         'ammo_type': 'phantom',
         'ammofile': '',
         'autocases': 0,
         'cache_dir': None,
         'chosen_cases': '',
         'client_certificate': '',
         'client_cipher_suites': '',
         'client_key': '',
         'connection_test': True,
         'file_cache': 8192,
         'force_stepping': 0,
         'headers': [],
         'loop': -1,
         'port': '',
         'use_caching': True,
         'multi': [],
         'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 10m)'},
     }
     }
     ),
    ({'phantom': {
        'package': 'yandextank.plugins.Phantom',
        'enabled': True,
        'load_profile': {
            'load_type': 'rps',
            'schedule': 'const(2,1m)'},
        'timeout': '5s',
        'uris': ['/'],
        'loop': 1000,
        'address': 'centurion.tanks.yandex.net'}},
     {'phantom': {
         'package': 'yandextank.plugins.Phantom',
         'enabled': True,
         'load_profile': {
             'load_type': 'rps',
             'schedule': 'const(2,1m)'},
         'timeout': '5s',
         'uris': ['/'],
         'loop': 1000,
         'address': 'centurion.tanks.yandex.net',
         'buffered_seconds': 2,
         'phantom_path': 'phantom',
         'affinity': '',
         'enum_ammo': False,
         'phout_file': '',
         'phantom_modules_path': '/usr/lib/phantom',
         'threads': None,
         'writelog': '0',
         'additional_libs': [],
         'config': '',
         'gatling_ip': '',
         'instances': 1000,
         'method_options': '',
         'method_prefix': 'method_stream',
         'phantom_http_entity': '8M',
         'phantom_http_field': '8K',
         'phantom_http_field_num': 128,
         'phantom_http_line': '1K',
         'source_log_prefix': '',
         'ssl': False,
         'tank_type': 'http',
         'ammo_limit': -1,
         'ammo_type': 'phantom',
         'ammofile': '',
         'autocases': 0,
         'cache_dir': None,
         'chosen_cases': '',
         'client_certificate': '',
         'client_cipher_suites': '',
         'client_key': '',
         'connection_test': True,
         'file_cache': 8192,
         'force_stepping': 0,
         'headers': [],
         'port': '',
         'use_caching': True,
         'header_http': '1.0',
         'multi': []},
      'core': {
          'artifacts_base_dir': './logs',
          'lock_dir': '/var/lock/',
          'taskset_path': 'taskset',
          'affinity': '',
          'ignore_lock': False}}
     )
])
def test_validate_core(config, expected):
    validated, errors, initial = TankConfig(config, False).validate()
    assert validated.validated == expected, errors == errors


@pytest.mark.parametrize('config, expected', [
    # plugins: no package
    ({
     "version": "1.9.3",
     "core": {
         'operator': 'fomars'
     },
     'telegraf': {
         'enabled': True,
         'config': 'monitoring.xml',
         'disguise_hostnames': 1
     },
     'phantom': {
         'package': 'yandextank.plugins.Phantom',
         'enabled': True,
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
         'uris': ['/'],
         'affinity': '',
         'enum_ammo': False,
         'phout_file': '',
         'config': '',
         'gatling_ip': '',
         'instances': 1000,
         'method_options': '',
         'method_prefix': 'method_stream',
         'phantom_http_entity': '8M',
         'phantom_http_field': '8K',
         'phantom_http_field_num': 128,
         'phantom_http_line': '1K',
         'source_log_prefix': '',
         'ssl': False,
         'tank_type': 'http',
         'multi': [],
     }
     }, {'telegraf': [{'package': ['required field']}]}),
    # plugins: empty package
    ({
     "version": "1.9.3",
     "core": {
         'operator': 'fomars'
     },
     'telegraf': {
         'package': '',
         'enabled': True,
         'config': 'monitoring.xml',
         'disguise_hostnames': 1
     },
     'phantom': {
         'package': 'yandextank.plugins.Phantom',
         'enabled': True,
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
         'uris': ['/']}
     }, {'telegraf': [{'package': ['empty values not allowed']}]})
])
def test_validate_core_error(config, expected):
    with pytest.raises(Exception) as e:
        TankConfig(config).validated
        print('exception value:\n', str(e.value))
    assert expected == e.value.errors


@pytest.mark.parametrize('configs, expected', [
    # test disable plugin
    ([{
        "version": "1.9.3",
        "core": {
            'operator': 'fomars'
        },
        "plugins": {
            'telegraf': {
                'package': 'yandextank.plugins.Telegraf',
                'enabled': True,
                'config': 'mon.xml'
            },
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'address': 'foo.bar'
            }
        }
    },
        {
        "version": "1.9.3",
        "core": {
            'operator': 'fomars'
        },
        "plugins": {
            'telegraf': {
                'package': 'yandextank.plugins.Telegraf',
                'enabled': False,
                'config': 'mon.xml'
            },
        }
    }
    ],
        {"version": "1.9.3",
         "core": {
             'operator': 'fomars'
         },
         "plugins": {
             'telegraf': {
                 'package': 'yandextank.plugins.Telegraf',
                 'enabled': False,
                 'config': 'mon.xml'
             },
             'phantom': {
                 'package': 'yandextank.plugins.Phantom',
                 'enabled': True,
                 'address': 'foo.bar'
             }
         }
         }
    )
])
def test_load_multiple(configs, expected):
    assert TankConfig(configs).raw_config_dict == expected


@pytest.mark.parametrize('config, expected', [
    (
        {
            "version": "1.9.3",
            "core": {
                'operator': 'fomars',
                'artifacts_base_dir': './'
            },
            'telegraf': {
                'package': 'yandextank.plugins.Telegraf',
                'enabled': True,
                'config': 'monitoring.xml',
                'disguise_hostnames': True
            },
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'address': 'nodejs.load.yandex.net',
                'header_http': '1.1',
                'uris': ['/'],
                'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 10m)'},
                'multi': [{'name': 'foo'}],
            }
        },
        {
            "version": "1.9.3",
            "core": {
                'operator': 'fomars',
                'artifacts_base_dir': './',
                'lock_dir': '/var/lock/',
                'taskset_path': 'taskset',
                'affinity': '',
                'ignore_lock': False
            },
            'telegraf': {
                'package': 'yandextank.plugins.Telegraf',
                'enabled': True,
                'config': 'monitoring.xml',
                'disguise_hostnames': True,
                'ssh_timeout': '5s',
                'default_target': 'localhost',
                'kill_old': False
            },
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'address': 'nodejs.load.yandex.net',
                'header_http': '1.1',
                'uris': ['/'],
                'buffered_seconds': 2,
                'phantom_path': 'phantom',
                'affinity': '',
                'enum_ammo': False,
                'phout_file': '',
                'phantom_modules_path': '/usr/lib/phantom',
                'threads': None,
                'writelog': '0',
                'timeout': '11s',
                'additional_libs': [],
                'config': '',
                'gatling_ip': '',
                'instances': 1000,
                'method_options': '',
                'method_prefix': 'method_stream',
                'phantom_http_entity': '8M',
                'phantom_http_field': '8K',
                'phantom_http_field_num': 128,
                'phantom_http_line': '1K',
                'source_log_prefix': '',
                'ssl': False,
                'tank_type': 'http',
                'ammo_limit': -1,
                'ammo_type': 'phantom',
                'ammofile': '',
                'autocases': 0,
                'cache_dir': None,
                'chosen_cases': '',
                'client_certificate': '',
                'client_cipher_suites': '',
                'client_key': '',
                'connection_test': True,
                'file_cache': 8192,
                'force_stepping': 0,
                'headers': [],
                'loop': -1,
                'port': '',
                'use_caching': True,
                'multi': [{'name': 'foo'}],
                'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 10, 10m)'}
            }
        }
    ),
])
def test_validate_all(config, expected):
    assert TankConfig(config, False).validated == expected


@pytest.mark.parametrize('config, expected', [
    # core errors
    (
        {
            "version": 5,
            "core": {},
            'telegraf': {
                'package': 'yandextank/plugins/Telegraf',
                'enabled': True,
                'config': 'monitoring.xml',
                'disguise_hostnames': True
            },
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'address': 'nodejs.load.yandex.net',
                'header_http': '1.1',
                'uris': ['/'],
            }
        },
        {'telegraf': [{'package': ["value does not match regex '[^/]+'"]}],
         'version': ['must be of string type']}),
    # plugins errors
    (
        {
            "version": "1.9.3",
            "core": {
                'operator': 'fomars',
                'artifacts_base_dir': './'
            },
            'telegraf': {
                'package': 'yandextank.plugins.Telegraf',
                'enabled': True,
                'config': 0,
                'disguise_hostnames': True
            },
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'header_http': '1.1',
                'uris': ['/'],
            }

        },
        {'phantom': {'address': ['required field'], 'load_profile': ['required field']},
         'telegraf': {'config': ['must be of string type']}}),
    (
        {
            "core": {},
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'address': 'nodejs.load.yandex.net',
                'uris': ['/'],
                'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 20, 2, 10m)'}
            }
        },
        {'phantom': {'load_profile': [{'schedule': ['line load scheme: expected 3 arguments, found 4']}]}}),
    (
        {
            "core": {},
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'address': 'nodejs.load.yandex.net',
                'uris': ['/'],
                'load_profile': {'load_type': 'rps', 'schedule': 'line(1, 20, 10m5m)'}
            }
        },
        {'phantom': {'load_profile': [{'schedule': ['Load duration examples: 2h30m; 5m15; 180']}]}}),
    (
        {
            "core": {},
            'phantom': {
                'package': 'yandextank.plugins.Phantom',
                'enabled': True,
                'address': 'nodejs.load.yandex.net',
                'uris': ['/'],
                'load_profile': {'load_type': 'rps', 'schedule': 'line(1n,20,100)'}
            }
        },
        {'phantom': {'load_profile': [{'schedule': ['Argument 1n in load scheme should be a number']}]}})

])
def test_validate_all_error(config, expected):
    with pytest.raises(ValidationError) as e:
        TankConfig(config).validated(config)
    assert e.value.errors == expected


@pytest.mark.parametrize('config, expected', [
    (
        CFG_VER_I_0,
        {
            (
                'telegraf',
                'yandextank.plugins.Telegraf',
            ),
            (
                'phantom',
                'yandextank.plugins.Phantom',
            ),
            (
                'lunapark',
                'yandextank.plugins.DataUploader',
            ),
            (
                'overload',
                'yandextank.plugins.DataUploader',
            )
        }
    )
])
def test_get_plugins(config, expected):
    validated, errors, raw = TankConfig(config).validate()
    assert {(name, pack) for name, pack, cfg in validated.plugins} == expected


@pytest.mark.parametrize('value', [
    'step(10,200,5,180)',
    'step(5,50,2.5,5m)',
    'line(22,154,2h5m)',
    'step(5,50,2.5,5m) line(22,154,2h5m)',
    'const(10,1h4m3s)',
    'const(2.5,150)',
    'const(100, 1d2h)',
    'line(10, 120, 300s)',
])
def test_load_scheme_validator(value):
    validator = PatchedValidator({'load_type': {'type': 'string'}, 'schedule': {'validator': 'load_scheme'}})
    cfg = {'load_type': 'rps', 'schedule': value}
    assert validator.validate(cfg)


@pytest.mark.parametrize('value', [
    'step(10,5,180)',
    'step(5,50,2.5,5m,30s)',
    'lien(22,154,2h5m)',
    'step(5,50,2.5,5m) line(22,154,2h5m) const(10, 20, 3m)',
    'const(10,1.5h)',
])
def test_negative_load_scheme_validator(value):
    validator = PatchedValidator({'load_type': {'type': 'string'}, 'schedule': {'validator': 'load_scheme'}})
    cfg = {'load_type': 'rps', 'schedule': value}
    assert not validator.validate(cfg)
