OPTIONS = {
    "additional_libs": {
        "type": "list",
        "default": [],
        'description': 'Libs for Phantom, to be added to phantom config file in section "module_setup"',
        'schema': {
            'type': 'string'
        }
    },
    "address": {
        'description': 'Address of target. Format: [host]:port, [ipv4]:port, [ipv6]:port. Port is optional. '
                       'Tank checks each test if port is available',
        "type": "string",
        "required": True,
        'examples': {'127.0.0.1:8080': '', 'www.w3c.org': ''}
    },
    'autocases': {
        'description': 'Use to automatically tag requests. Requests might be grouped by tag for later analysis.',
        'anyof': [
            {'type': 'integer'},
            {'type': 'string',
             'allowed': ['uri', 'uniq']}],
        'default': 0,
        'values_description': {
            'uri': 'tag each request with its uri path, slashes are replaced with underscores',
            'uniq': 'tag each request with unique uid',
            '<N>': 'use N first uri parts to tag request, slashes are replaced with underscores'
        },
        'examples': {
            2: '/example/'
               'search/hello/help/us?param1=50 -> _example_search',
            3: '/example/search/hello/help/us?param1=50 -> _example_search_hello',
            'uri': '/example/search/hello/help/us?param1=50 -> _example_search_hello_help_us',
            'uniq': '/example/search/hello/help/us?param1=50 -> c98b0520bb6a451c8bc924ed1fd72553'
        }
    },
    "affinity": {
        "type": "string",
        "default": ""
    },
    'ammo_limit': {
        'type': 'integer',
        'default': -1
    },
    'ammo_type': {
        'type': 'string',
        'default': 'phantom'
    },
    'ammofile': {
        'type': 'string',
        'default': ''
    },
    "buffered_seconds": {
        "type": "integer",
        "default": 2
    },
    'cache_dir': {
        'type': 'string',
        'nullable': True,
        'default': None
    },
    'chosen_cases': {
        'type': 'string',
        'default': ''
    },
    'client_certificate': {
        'type': 'string',
        'default': ''
    },
    'client_cipher_suites': {
        'type': 'string',
        'default': ''
    },
    'client_key': {
        'type': 'string',
        'default': ''
    },
    'config': {
        'type': 'string',
        'default': '',
    },
    'connection_test': {
        'type': 'boolean',
        'default': True
    },
    "enum_ammo": {
        "type": "boolean",
        "default": False
    },
    'file_cache': {
        'type': 'integer',
        'default': 8192
    },
    'force_stepping': {
        'type': 'integer',
        'default': 0
    },
    'gatling_ip': {
        'type': 'string',
        'default': ''
    },
    "header_http": {
        "type": "string",
        'default': '1.0'
    },
    "headers": {
        "type": "string",
        'default': ''
    },
    'instances': {
        'type': 'integer',
        'default': 1000
    },
    'loop': {
        'type': 'integer',
        'default': -1
    },
    'method_options': {
        'type': 'string',
        'default': ''
    },
    'method_prefix': {
        'type': 'string',
        'default': 'method_stream'
    },
    'phantom_http_entity': {
        'type': 'string',
        'default': ''
    },
    'phantom_http_field': {
        'type': 'string',
        'default': ''
    },
    'phantom_http_field_num': {
        'type': 'string',
        'default': ''
    },
    'phantom_http_line': {
        'type': 'string',
        'default': ''
    },
    "phantom_modules_path": {
        "type": "string",
        "default": "/usr/lib/phantom"
    },
    "phantom_path": {
        "type": "string",
        "default": "phantom"
    },
    "phout_file": {
        "type": "string",
        'description': 'deprecated',
        "default": ""
    },
    'port': {
        'type': 'string',
        'default': '',
        'regex': '\d{0,5}'
    },
    "load_profile": {
        "type": "dict",
        'schema': {
            'load_type': {
                'type': 'string',
                'allowed': ['rps', 'instances', 'stpd_file'],
                'values_description': {
                    'rps': 'fix rps rate',
                    'instances': 'fix number of instances',
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
        'required': True
    },
    'source_log_prefix': {
        'type': 'string',
        'default': ''
    },
    'ssl': {
        'type': 'boolean',
        'default': False
    },
    "threads": {
        "type": "integer",
        "default": None,
        "nullable": True
    },
    'tank_type': {
        'type': 'string',
        'default': 'http'
    },
    "timeout": {
        "type": "string",
        "default": "11s"
    },
    "uris": {
        "type": "string",
        'default': ''
    },
    'use_caching': {
        'type': 'boolean',
        'default': True
    },
    "writelog": {
        "type": "string",
        "default": "none"
    }
}

MULTI = {
    'multi': {
        'type': 'list',
        'allow_unknown': True,
        'schema': OPTIONS,
        'default': []}
}


def compile_schema():
    schema = OPTIONS.copy()
    schema.update(MULTI)
    return schema


SCHEMA = compile_schema()
