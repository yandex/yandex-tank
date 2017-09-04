OPTIONS = {
    "additional_libs": {
        "type": "string",
        "default": ""
    },
    "address": {
        "type": "string",
        "required": True
    },
    'autocases': {
        'type': 'string',
        'default': '0'
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
                'regex': '^rps|instances|stpd_file$',
                'required': True
            },
            'schedule': {
                'type': 'string',
                'required': True
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
