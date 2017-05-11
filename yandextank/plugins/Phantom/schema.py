OPTIONS = {
    "additional_libs": {
        "type": "string",
        "default": ""
    },
    "address": {
        "type": "string",
        "required": True
    },
    "affinity": {
        "type": "string",
        "default": ""
    },
    "buffered_seconds": {
        "type": "integer",
        "default": 2
    },
    'config': {
        'type': 'string',
        'default': '',
    },
    "enum_ammo": {
        "type": "boolean",
        "default": False
    },
    'gatling_ip': {
        'type': 'string',
        'default': ''
    },
    "header_http": {
        "type": "string"
    },
    "headers": {
        "type": "string"
    },
    'instances': {
        'type': 'integer',
        'default': 1000
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
    "rps_schedule": {
        "type": "string"
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
        "type": "string"
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
