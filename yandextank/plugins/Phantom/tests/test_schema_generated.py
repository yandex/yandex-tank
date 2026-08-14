import pkg_resources

from yandextank.plugins.Phantom.config.generate_schema_yaml import render


def test_generated_schema_matches_source():
    """schema_generated.yaml обязан совпадать со схемой из schema.py.

    Сгенерированный YAML читают потребители вне Python (MCP gateway вкомпилирует его
    в бинарь и валидирует им конфиги), поэтому разъехавшийся файл — не косметика,
    а неверная валидация у пользователя.
    """
    stored = pkg_resources.resource_string('yandextank.plugins.Phantom', 'config/schema_generated.yaml').decode()

    assert stored == render(), (
        'schema_generated.yaml разошёлся со schema.py; перегенерируйте: '
        'python3 -m yandextank.plugins.Phantom.config.generate_schema_yaml'
    )
