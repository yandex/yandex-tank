# coding=utf-8
import pytest
from yandextank.validator.docs_gen import RSTRenderer, format_option


@pytest.mark.parametrize('option_schema, expected', [
    ({'report_file': {
        'description': 'path to file to store autostop report',
        'type': 'string',
        'default': 'autostop_report.txt'}
     }, ur"""``report_file`` (string)
------------------------
*\- path to file to store autostop report. Default:* ``autostop_report.txt``"""),
    ({'gun_type': {
        'type': 'string',
        'description': 'gun type',
        'allowed': ['custom', 'http', 'scenario', 'ultimate'],
        # 'values_description': {
        #     'custom': 'custom gun', 'http': 'http gun', 'scenario': 'scenario gun', 'ultimate': 'ultimate gun'
        # },
        'required': 'true'}
     }, ur"""``gun_type`` (string)
---------------------
*\- gun type.* **Required.**

:one of: [``custom``, ``http``, ``scenario``, ``ultimate``]"""),
    ({'gun_type': {
        'type': 'string',
        'description': 'gun type',
        'allowed': ['custom', 'http', 'scenario', 'ultimate'],
        'values_description': {
            'custom': 'custom gun', 'http': 'http gun', 'scenario': 'scenario gun', 'ultimate': 'ultimate gun'
        },
        'required': 'true'}
     }, ur"""``gun_type`` (string)
---------------------
*\- gun type.* **Required.**

:one of:
 :``custom``: custom gun
 :``http``: http gun
 :``scenario``: scenario gun
 :``ultimate``: ultimate gun"""),
    ({"load_profile": {
        "type": "dict",
        'description': 'specify parameters of your load',
        'schema': {
            'load_type': {
                'type': 'string',
                'required': 'true',
                'description': 'choose your load type',
                'allowed': ['rps', 'instances', 'stpd_file'],
                'values_description': {
                    'instances': 'fix number of instances',
                    'rps': 'fix rps rate',
                    'stpd_file': 'use ready schedule file'}
            },
            'schedule': {
                'type': 'string',
                'required': True,
                'description': 'load schedule or path to stpd file',
                'examples': {
                    'line(100,200,10m)': 'linear growth from 100 to 200 instances/rps during 10 minutes',
                    'const(200,90s)': 'constant load of 200 instances/rps during 90s',
                    'test_dir/test_backend.stpd': 'path to ready schedule file'}
            }
        },
        'required': True}
     }, ur"""``load_profile`` (dict)
-----------------------
*\- specify parameters of your load.* **Required.**

:``load_type`` (string):
 *\- choose your load type.* **Required.**
 
 :one of:
  :``instances``: fix number of instances
  :``rps``: fix rps rate
  :``stpd_file``: use ready schedule file
:``schedule`` (string):
 *\- load schedule or path to stpd file.* **Required.**
 
 :examples:
  ``const(200,90s)``
   constant load of 200 instances/rps during 90s
  ``line(100,200,10m)``
   linear growth from 100 to 200 instances/rps during 10 minutes
  ``test_dir/test_backend.stpd``
   path to ready schedule file"""),  # noqa: W293
    ({'lock_targets': {
        'default': 'auto',
        'description': 'targets to lock',
        'values_description': {
            'auto': 'automatically identify target host',
            '[ya.ru, ...]': 'list of targets to lock'
        },
        'anyof': [
            {'type': 'list'},
            {'type': 'string', 'allowed': ['auto']}
        ],
        'tutorial_link': 'http://yandextank.readthedocs.io'}
     }, ur"""``lock_targets`` (list or string)
---------------------------------
*\- targets to lock. Default:* ``auto``

:one of:
 :``[ya.ru, ...]``: list of targets to lock
 :``auto``: automatically identify target host

:tutorial_link:
 http://yandextank.readthedocs.io"""),
    ({'autostop': {
        'description': 'list of autostop constraints',
        'type': 'list',
        'schema': {
            'type': 'string',
            'description': 'autostop constraint',
            'examples': {'http(4xx,50%,5)': 'stop when rate of 4xx http codes is 50% or more during 5 seconds'}
        },
        'default': []}
     }, ur"""``autostop`` (list of string)
-----------------------------
*\- list of autostop constraints. Default:* ``[]``

:[list_element] (string):
 *\- autostop constraint.*
 
 :examples:
  ``http(4xx,50%,5)``
   stop when rate of 4xx http codes is 50% or more during 5 seconds""")  # noqa: W293
])
def test_format_option(option_schema, expected):
    assert format_option(option_schema, RSTRenderer) == expected
