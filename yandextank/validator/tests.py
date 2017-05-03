

import pytest

from validator import TankConfig, ValidationError

CFG_VER_I_0 = {
    "version": "1.8.34",
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
        'uris': '/',
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
        'regex': '(\[[\w\d\.]+:\s[\w\d\.]+\]\s*)+'
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
         "version": "1.8.34",
         "core": {
             'operator': 'fomars',
             'artifacts_base_dir': './',
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
             'uris': '/',
         }
     },
     {
         "version": "1.8.34",
         "core": {
             'operator': 'fomars',
             'artifacts_base_dir': './',
             'lock_dir': '/var/lock/',
             'taskset_path': 'taskset',
             'affinity': '',
         },
         'telegraf': {
             'package': 'yandextank.plugins.Telegraf',
             'enabled': True,
             'config': 'monitoring.xml',
             'disguise_hostnames': True,
             'default_target': 'localhost',
             'ssh_timeout': '5s',
         },
         'phantom': {
             'package': 'yandextank.plugins.Phantom',
             'enabled': True,
             'address': 'nodejs.load.yandex.net',
             'header_http': '1.1',
             'uris': '/',
             'buffered_seconds': 2,
             'phantom_path': 'phantom',
         }
     }
    )
])
def test_validate_core(config, expected):
    assert TankConfig(config).validated == expected


@pytest.mark.parametrize('config, expected', [
    # plugins: no package
    ({
         "version": "1.8.34",
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
             'uris': '/',
         }

     }, "{'package': ['required field']}"),
    # plugins: empty package
    ({
         "version": "1.8.34",
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
             'uris': '/',
         }

     }, '{\'telegraf\': [{\'package\': [\'empty values not allowed\', "value does not match regex \'[^/]+\'"]}]}')
])
def test_validate_core_error(config, expected):
    with pytest.raises(Exception) as e:
        TankConfig(config).validated
    assert expected in str(e.value)


@pytest.mark.parametrize('configs, expected', [
    # test disable plugin
    ([
         {"version": "1.8.34",
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
         {"version": "1.8.34",
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
     {"version": "1.8.34",
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
    assert TankConfig(*configs)._TankConfig__raw_config_dict == expected


@pytest.mark.parametrize('config, schema, expected', [
    # simple
    ({
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
         'uris': '/',
         'headers': '[Host: nodejs.load.yandex.net]\n[Connection: close]',
         'rps_schedule': 'line(1, 10, 30s)',
         'writelog': 'all',
         'buffered_seconds': 5,
         'phantom_path': './phantom'
     },
     PHANTOM_SCHEMA_V_G,
     {
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
         'uris': '/',
         'headers': '[Host: nodejs.load.yandex.net]\n[Connection: close]',
         'rps_schedule': 'line(1, 10, 30s)',
         'writelog': 'all',
         'buffered_seconds': 5,
         'phantom_path': './phantom'
     }
    ),
    # defaults
    ({
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
     },
     PHANTOM_SCHEMA_V_G,
     {
         'address': 'nodejs.load.yandex.net',
         'header_http': '1.1',
         'buffered_seconds': 2,
         'phantom_path': 'phantom'
     }
    )
])
def test_validate_plugin(config, schema, expected):
    assert TankConfig._TankConfig__validate_plugin(config, schema) == expected


@pytest.mark.parametrize('config, schema, expected', [
    # no address
    ({
         'header_http': '1.1',
         'uris': '/',
         'headers': '[Host: nodejs.load.yandex.net]\n[Connection: close]',
         'rps_schedule': 'line(1, 10, 30s)',
         'writelog': 'all',
         'buffered_seconds': 5,
         'phantom_path': './phantom'
     },
     PHANTOM_SCHEMA_V_G,
     {'address': ['required field']}),
    ({
         'header_http': '1.1',
         'uris': '/',
         'headers': '[Host: nodejs.load.yandex.net]\n[Connection: close]',
         'rps_schedule': 'line(1, 10, 30s)',
         'writelog': 'all',
         'buffered_seconds': 'foo',
         'phantom_path': './phantom'
     },
     PHANTOM_SCHEMA_V_G,
     {'address': ['required field'], 'buffered_seconds': ['must be of integer type']})
])
def test_validate_plugin_error(config, schema, expected):
    with pytest.raises(ValidationError) as e:
        TankConfig._TankConfig__validate_plugin(config, schema)
    assert expected == e.value.message


@pytest.mark.parametrize('config, expected', [
    ({
         "version": "1.8.34",
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
             'uris': '/',
         }
     },
     {
         "version": "1.8.34",
         "core": {
             'operator': 'fomars',
             'artifacts_base_dir': './',
             'lock_dir': '/var/lock/',
             'taskset_path': 'taskset',
             'affinity': '',
         },
         'telegraf': {
             'package': 'yandextank.plugins.Telegraf',
             'enabled': True,
             'config': 'monitoring.xml',
             'disguise_hostnames': True,
             'ssh_timeout': '5s',
             'default_target': 'localhost'
         },
         'phantom': {
             'package': 'yandextank.plugins.Phantom',
             'enabled': True,
             'address': 'nodejs.load.yandex.net',
             'header_http': '1.1',
             'uris': '/',
             'buffered_seconds': 2,
             'phantom_path': 'phantom'
         }
     }
    ),
])
def test_validate_all(config, expected):
    assert TankConfig(config).validated == expected


@pytest.mark.parametrize('config, expected', [
    # core errors
    ({
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
             'uris': '/',
         }
     },
     {'telegraf': [{'package': ["value does not match regex '[^/]+'"]}],
      'version': ['must be of string type']}),
    # plugins errors
    ({
         "version": "1.8.34",
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
             'uris': '/',
         }

     },
     {'phantom': {'address': ['required field']},
      'telegraf': {'config': ['must be of string type']}})
])
def test_validate_all_error(config, expected):
    with pytest.raises(ValidationError) as e:
        TankConfig(config).validated(config)
    assert e.value.message == expected


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
    assert {(name, pack) for name, pack, cfg in TankConfig(config).plugins} == expected



    # configparser = ConfigParser.ConfigParser()
    # configparser.read(config_file)
    # plugins_conf = {section: dict(configparser.items(section)) for section in configparser.sections()}
    # config = {
    #     "version": "1.8.34",
    #     "core": {
    #           'operator': 'fomars'
    #       },
    #     "plugins": plugins_conf
    # }
