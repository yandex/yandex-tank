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
        "empty": False,
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
        'description': 'Use to set CPU affinity',
        "type": "string",
        "default": '',
        'examples': {
            '0-3': 'enable first 4 cores',
            '0,1,2,16,17,18': 'enable 6 specified cores'
        }
    },
    'ammo_limit': {
        'description': 'Sets the upper limit for the total number of requests',
        'type': 'integer',
        'default': -1
    },
    'ammo_type': {
        'description': 'Ammo format. Don\'t forget to change ammo_type option if you switch the format of your ammo, otherwise you might get errors',
        'type': 'string',
        'default': 'phantom',
        'allowed': ['phantom', 'uri', 'uripost', 'access'],
        'values_description': {
            'phantom': 'Use Request-style file. Most versatile, HTTP as is. See tutorial for details',
            'uri': 'Use URIs listed in file with headers. Simple but allows for GET requests only. See tutorial for details',
            'uripost': 'Use URI-POST file. Allows POST requests with bodies. See tutorial for details',
            'access': 'Use access.log from your web server as a source of requests'
        },
        'tutorial_link': 'http://yandextank.readthedocs.io/en/latest/tutorial.html#preparing-requests'
    },
    'ammofile': {
        'type': 'string',
        'default': '',
        'description': 'Path to ammo file. Ammo file contains requests to be sent to a server. Can be gzipped',
        'tutorial_link': 'http://yandextank.readthedocs.io/en/latest/tutorial.html#preparing-requests',
    },
    "buffered_seconds": {
        "type": "integer",
        "default": 2,
        'description': 'Aggregator latency'
    },
    'cache_dir': {
        'type': 'string',
        'nullable': True,
        'default': None,
        'description': 'stpd-file cache directory'
    },
    'chosen_cases': {
        'type': 'string',
        'default': '',
        'description': 'Use only selected cases.'
    },
    'client_certificate': {
        'type': 'string',
        'default': '',
        'description': 'Path to client SSL certificate'
    },
    'client_cipher_suites': {
        'type': 'string',
        'default': '',
        'description': 'Cipher list, consists of one or more cipher strings separated by colons (see man ciphers)',
    },
    'client_key': {
        'type': 'string',
        'default': '',
        'description': 'Path to client\'s certificate\'s private key'
    },
    'config': {
        'type': 'string',
        'default': '',
        'description': 'Use ready phantom config instead of generated'
    },
    'connection_test': {
        'type': 'boolean',
        'default': True,
        'description': 'Test TCP socket connection before starting the test'
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
        'default': 0,
        'description': 'Ignore cached stpd files, force stepping'
    },
    'gatling_ip': {
        'type': 'string',
        'default': ''
    },
    "header_http": {
        "type": "string",
        'default': '1.0',
        'description': 'HTTP version',
        'allowed': ['1.0', '1.1'],
        'values_description': {
            '1.0': 'http 1.0',
            '1.1': 'http 1.1'
        }
    },
    "headers": {
        "type": "list",
        'default': [],
        'description': 'HTTP headers',
        'schema': {
            'description': 'Format: "Header: Value"',
            'type': 'string',
            'examples': {'accept: text/html': ''}
        }
    },
    'instances': {
        'description': 'Max number of concurrent clients.',
        'type': 'integer',
        'default': 1000
    },
    'loop': {
        'description': 'Loop over ammo file for the given amount of times.',
        'type': 'integer',
        'default': -1
    },
    'method_options': {
        'description': 'Additional options for method objects. It is used for Elliptics etc.',
        'type': 'string',
        'default': ''
    },
    'method_prefix': {
        'description': 'Object\'s type, that has a functionality to create test requests.',
        'type': 'string',
        'default': 'method_stream'
    },
    'multi': {
        'type': 'list',
        'schema': {'type': 'dict'},
        'default': [],
        'description': 'List of configs for multi-test. All of the options from main config supported. All of them not required and inherited from main config if not specified'
    },
    'name': {
        'description': 'Name of a part in multi config',
        'type': 'string',
        'required': False
    },
    'phantom_http_entity': {
        'type': 'string',
        'default': '8M',
        'description': 'Limits the amount of bytes Phantom reads from response.'
    },
    'phantom_http_field': {
        'type': 'string',
        'default': '8K',
        'description': 'Header size.'
    },
    'phantom_http_field_num': {
        'type': 'integer',
        'default': 128,
        'description': 'Max number of headers'
    },
    'phantom_http_line': {
        'type': 'string',
        'default': '1K',
        'description': 'First line length'
    },
    "phantom_modules_path": {
        "type": "string",
        "default": "/usr/lib/phantom",
        'description': 'Phantom modules path.'
    },
    "phantom_path": {
        'description': 'Path to Phantom binary',
        "type": "string",
        "default": "phantom"
    },
    "phout_file": {
        "type": "string",
        'description': 'deprecated',
        "default": ""
    },
    'port': {
        'description': 'Explicit target port, overwrites port defined with address',
        'type': 'string',
        'default': '',
        'regex': r'\d{0,5}'
    },
    "load_profile": {
        'description': 'Configure your load setting the number of RPS or instances (clients) as a function of time,'
                       'or using a prearranged schedule',
        "type": "dict",
        'tutorial_link': 'http://yandextank.readthedocs.io/en/latest/tutorial.html#tutorials',
        'schema': {
            'load_type': {
                'required': True,
                'description': 'Choose control parameter',
                'type': 'string',
                'allowed': ['rps', 'instances', 'stpd_file'],
                'values_description': {
                    'rps': 'control the rps rate',
                    'instances': 'control the number of instances',
                    'stpd_file': 'use prearranged schedule file'}
            },
            'schedule': {
                'type': 'string',
                'required': True,
                'description': 'load schedule or path to stpd file',
                'examples': {
                    'line(100,200,10m)': 'linear growth from 100 to 200 instances/rps during 10 minutes',
                    'const(200,90s)': 'constant load of 200 instances/rps during 90s',
                    'test_dir/test_backend.stpd': 'path to ready schedule file'},
                'validator': 'load_scheme'
            }
        },
        'required': True
    },
    'source_log_prefix': {
        'description': 'Prefix added to class name that reads source data',
        'type': 'string',
        'default': ''
    },
    'ssl': {
        'description': 'Enable ssl',
        'type': 'boolean',
        'default': False
    },
    "threads": {
        'description': 'Phantom thread count. When not specified, defaults to <processor cores count> / 2 + 1',
        "type": "integer",
        "default": None,
        "nullable": True
    },
    'tank_type': {
        'description': 'Choose between http and pure tcp guns',
        'type': 'string',
        'default': 'http',
        'allowed': ['http', 'none'],
        'values_description': {
            'http': 'HTTP gun',
            'none': 'TCP gun'
        }
    },
    "timeout": {
        'description': 'Response timeout',
        "type": "string",
        "default": "11s"
    },
    "uris": {
        "type": "list",
        'default': [],
        'description': 'URI list',
        'schema': {
            'type': 'string',
            'description': 'URI path string'
        },
        'examples': {
            '["/example/search", "/example/search/hello", "/example/search/hello/help"]': ''
        }
    },
    'use_caching': {
        'description': 'Enable stpd-file caching for similar tests. Set false to reload ammo file and generate new stpd',
        'type': 'boolean',
        'default': True
    },
    "writelog": {
        'description': 'Enable verbose request/response logging.',
        "type": "string",
        "default": "0",
        'allowed': ['0', 'all', 'proto_warning', 'proto_error'],
        'values_description': {
            '0': 'disable',
            'all': 'all messages',
            'proto_warning': '4xx+5xx+network errors',
            'proto_error': '5xx+network errors',
        }
    }
}


MULTI_OPTIONS = {n: {k: v for k, v in d.items() if k != 'required' and k != 'default'} for n, d in OPTIONS.items()}


MULTI = {
    'multi': {
        'type': 'list',
        'allow_unknown': True,
        'schema': {'type': 'dict', 'schema': MULTI_OPTIONS},
        'default': []}
}


def compile_schema():
    schema = OPTIONS.copy()
    schema.update(MULTI)
    return schema


SCHEMA = compile_schema()
