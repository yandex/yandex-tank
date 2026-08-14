"""Рендер схемы Phantom в YAML.

Схема плагина живёт в schema.py, потому что MULTI_OPTIONS вычисляется из OPTIONS.
Потребителям вне Python (например MCP gateway, который вкомпилирует схемы всех
плагинов в бинарь) нужен YAML, поэтому рядом лежит сгенерированный schema.yaml.
Расхождение стережёт tests/test_schema_generated.py.

Перегенерировать:
    python3 -m yandextank.plugins.Phantom.config.generate_schema_yaml
"""

import os

import yaml

from yandextank.plugins.Phantom.config.schema import SCHEMA

HEADER = "# Сгенерировано из schema.py, руками не править.\n# Перегенерация: python3 -m yandextank.plugins.Phantom.config.generate_schema_yaml\n"

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema_generated.yaml')


class NoAliasDumper(yaml.SafeDumper):
    """MULTI_OPTIONS переиспользует вложенные словари OPTIONS, из-за чего обычный
    дампер расставляет якоря и алиасы. Потребители схемы их разворачивают, но читать
    и ревьюить такой файл невозможно, поэтому пишем всё развёрнуто."""

    def ignore_aliases(self, data):
        return True


def render():
    return HEADER + yaml.dump(
        SCHEMA, Dumper=NoAliasDumper, allow_unicode=True, sort_keys=True, default_flow_style=False
    )


if __name__ == '__main__':
    with open(TARGET, 'w') as f:
        f.write(render())
