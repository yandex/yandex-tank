import argparse
from types import NoneType

import yaml


TYPE = 'type'
DESCRIPTION = 'description'
REQUIRED = 'required'
DEFAULT = 'default'
ALLOWED = 'allowed'
VALUES_DSC = 'values_description'
ONE_OF = 'one of'
SCHEMA = 'schema'
EXAMPLES = 'examples'


class TextBlock(object):
    def __init__(self, text, tab_replacement='  ', ending=''):
        """

        :type text: str
        """
        self.text = text.replace('\t', tab_replacement)
        self.lines = self.text.splitlines()
        self.width = max([len(line) for line in self.lines] + [0])
        self.padded_width = self.width + 2
        self.height = len(self.lines)

    def get_line(self, item, raise_index_error=False, default=''):
        try:
            return self.lines[item]
        except IndexError:
            if raise_index_error:
                raise
            else:
                return default

    def get_line_justified(self, item, fillchar=' ', raise_index_error=False, default=''):
        return self.get_line(item, raise_index_error, default).ljust(self.width, fillchar)

    def __str__(self):
        return self.text


def to_text_block(method):
    def decorated(content):
        if not isinstance(content, TextBlock):
            return method(TextBlock(content))
        else:
            return method(TextBlock)
    return decorated


class RSTRenderer(object):

    def with_escape(method):
        def escaped(content):
            return method(RSTRenderer.escape(content))
        return escaped

    @staticmethod
    def any_of_table(blocks):
        """

        :type blocks: list of TextBlock
        """
        HEADER = 'any of'
        cnt = len(blocks)
        # no need table for single content
        if cnt < 2:
            return blocks[0] if blocks else ''
        # width = widths of contents + separators
        width = max((len(HEADER), sum([c.padded_width for c in blocks]))) + (cnt + 1)
        height = max([c.height for c in blocks])
        # rows separators
        top_bar = '+{}+'.format('-' * (width - 2))
        header_bar = '+{}+'.format('+'.join(['=' * c.padded_width for c in blocks]))
        bottom_bar = '+{}+'.format('+'.join(['-' * c.padded_width for c in blocks]))

        header = '|{}|'.format(HEADER.center(width - 2))
        body = '\n'.join(
            ['| {} |'.format(' | '.join([c.get_line_justified(i) for c in blocks])) for i in range(height)])
        return '\n'.join([top_bar,
                          header,
                          header_bar,
                          body,
                          bottom_bar])

    @staticmethod
    def preserve_indents(block):
        """

        :type block: TextBlock
        """
        return '\n'.join(['| {}'.format(line) for line in block.lines])

    @staticmethod
    def bold(content):
        """
        :type content: str
        :return: str
        """
        return '\n'.join(['**{}**'.format(line) for line in content.splitlines()])


    @staticmethod
    def title(content, new_line_replacement=' ', tab_replacement='  '):
        """
        Underlines content with '='. New lines and tabs will be replaced
        :param str content:
        :param str new_line_replacement:
        :param str tab_replacement:
        :return: unicode
        """
        prepared_content = content.strip().replace('\n', new_line_replacement).replace('\t', tab_replacement)
        return u'{}\n{}'.format(prepared_content, '=' * len(prepared_content))

    @staticmethod
    def subtitle(content, new_line_replacement=' ', tab_replacement='  '):
        prepared_content = content.strip().replace('\n', new_line_replacement).replace('\t', tab_replacement)
        return u'{}\n{}'.format(prepared_content, '-' * len(prepared_content))

    @staticmethod
    @with_escape
    @to_text_block
    def italic(block):
        """

        :type block: TextBlock
        """
        return '\n'.join(['*{}*'.format(line) for line in block.lines])

    @staticmethod
    @to_text_block
    def mono(block):
        """

        :type block: TextBlock
        """
        return '\n'.join(['``{}``'.format(line) for line in block.lines])


    @classmethod
    def bullet_list(cls, blocks):
        """

        :type blocks: list of TextBlock
        :rtype: TextBlock
        """
        return TextBlock('\n'.join([cls._list_item(block) for block in blocks]))

    @staticmethod
    def _list_item(block):
        """

        :type block: TextBlock
        """
        return '- ' + '\n  '.join(block.lines)

    @staticmethod
    def field_list(items, sort=True, newlines=True):
        """

        :param bool newlines: add newlines between names and values
        :param bool sort: sort items alphabetically by key
        :type items: dict
        :rtype: TextBlock
        """

        def format_value(value):
            if isinstance(value, (int, bool, NoneType)):
                return format_value(str(value))
            if isinstance(value, str):
                return '\n '.join(value.splitlines())
            elif isinstance(value, TextBlock):
                return '\n '.join(value.lines)
            elif isinstance(value, dict):
                return '\n '.join(RSTRenderer.field_list(value, sort, newlines).splitlines())
            elif isinstance(value, list):
                return '\n '.join(RSTRenderer.bullet_list([TextBlock(item) for item in value]).lines)
            else:
                raise ValueError('Unsupported value type: {}\n{}'.format(type(value), value))

        sort = sorted if sort else lambda x: x
        template = ':{}:\n {}' if newlines else ':{}: {}'
        return '\n' + '\n'.join([template.format(k.replace('\n', ' '),
                                                 format_value(v).strip())
                                 for k, v in sort(items.items())]) if items else ''

    @staticmethod
    def dict_list_structure(items, sort_dict=True):
        if isinstance(items, str):
            return TextBlock(items)
        elif isinstance(items, int):
            return TextBlock(str(items))
        elif isinstance(items, list):
            return RSTRenderer.bullet_list([RSTRenderer.dict_list_structure(item) for item in items])
        elif isinstance(items, dict):
            return RSTRenderer.field_list({k: RSTRenderer.dict_list_structure(v) for k, v in items.items()}, sort_dict)

    @staticmethod
    def escape(content):
        """
        :type content: str
        """
        return content.replace('-', '\-')

    del with_escape


def render_dsc(renderer, option_kwargs):
    """

    :type option_kwargs: dict
    """
    if DEFAULT in option_kwargs:
        return renderer.italic('- {}. Default: '.format(option_kwargs.get(DESCRIPTION))) + \
               renderer.mono(option_kwargs.get(DEFAULT))
    elif REQUIRED in option_kwargs:
        return renderer.italic('- {}.'.format(option_kwargs.get(DESCRIPTION))) + ' ' +\
               renderer.bold('Required.')
    else:
        return renderer.italic('- {}.'.format(option_kwargs.get(DESCRIPTION)))


def render_body(renderer, option_kwargs, exclude_keys, special_keys=None):
    """

    :type option_kwargs: dict
    :type exclude_keys: list
    :type special_keys: dict
    """
    formatters = {
        'examples': lambda examples: {renderer.mono(example): note for example, note in examples.items()}
    }
    DEFAULT_FMT = lambda x: x
    special_keys = special_keys or {}
    special_part = '\n'.join([special_handler(renderer, option_kwargs[special_key])
                              for special_key, special_handler in special_keys.items()
                              if special_key in option_kwargs])
    common_part = renderer.field_list({k: formatters.get(k, DEFAULT_FMT)(v) for k, v in option_kwargs.items()
                                       if k not in exclude_keys + special_keys.keys()})

    return '\n'.join([_ for _ in [common_part, special_part] if _])


def allowed(renderer, values):
    return renderer.field_list({ONE_OF: '[{}]'.format(', '.join([renderer.mono(value) for value in values]))},
                               newlines=False)


def get_formatter(option_schema):
    """

    :type option_schema: dict
    """
    option_name, option_kwargs = option_schema.items()[0]

    def scalar_formatter(renderer):
        dsc = render_dsc(renderer, option_kwargs)
        body = render_body(renderer, option_kwargs, [TYPE, DESCRIPTION, DEFAULT, REQUIRED], {'allowed': allowed})
        return '\n'.join([_ for _ in [dsc, body] if _])

    def scalar_with_values_description(renderer):
        dsc = render_dsc(renderer, option_kwargs)
        body = render_body(renderer, option_kwargs, [TYPE, DESCRIPTION, DEFAULT, REQUIRED, ALLOWED, VALUES_DSC])
        values_description_dict = {
            value: option_kwargs[VALUES_DSC].get(value, '') for value in option_kwargs[ALLOWED]
        } \
            if ALLOWED in option_kwargs \
            else \
            option_kwargs[VALUES_DSC]
        values_description = renderer.field_list(
            {renderer.mono(value): dsc for value, dsc in values_description_dict.items()},
            newlines=False
        )
        values_description_block = renderer.field_list({ONE_OF: values_description})
        return '\n'.join([_ for _ in [dsc, body, values_description_block] if _])

    def dict_formatter(renderer):
        dsc = render_dsc(renderer, option_kwargs)

        dict_schema = option_kwargs[SCHEMA]
        schema_block = renderer.field_list({
            '{} ({})'.format(key, dict_schema[key][TYPE]): get_formatter({key: value})(renderer)
            for key, value in dict_schema.items()})
        body = render_body(renderer, option_kwargs, [TYPE, DESCRIPTION, DEFAULT, REQUIRED, SCHEMA])
        return '\n'.join([_ for _ in [dsc, schema_block, body] if _])

    if SCHEMA in option_kwargs:
        return dict_formatter
    if VALUES_DSC in option_kwargs:
        return scalar_with_values_description
    else:
        return scalar_formatter


def format_option(option_schema, renderer):
    option_name, option_kwargs = option_schema.items()[0]
    header = renderer.subtitle(renderer.bold(option_name) + ' ' + '({})'.format(option_kwargs.get(TYPE)))
    return header + '\n' + get_formatter(option_schema)(renderer)


def format_schema(schema, formatter):
    """

    :param dict schema: Cerberus config schema
    :type formatter: RSTRenderer
    """
    REQUIRED = 'required'
    DEFAULT = 'default'

    def get_default(_schema):
        """

        :type _schema: dict
        """
        if DEFAULT in _schema:
            return {DEFAULT: _schema[DEFAULT]}
        else:
            return {REQUIRED: _schema.get(REQUIRED, False)}

    return '\n'.join(['%s\n%s\n%s' % (formatter.title(key),
                                      formatter.field_list(get_default(value)),
                                      formatter.dict_list_structure({k: v for k, v in value.items()
                                                                     if k not in {REQUIRED, DEFAULT}}))
                      for key, value in schema.items()])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('schema', help='Path to schema file')
    parser.add_argument('output_filename', default='output.rst', help='Name for the output rst document')
    args = parser.parse_args()
    schema_path = args.schema
    output_filename = args.output_filename

    with open(schema_path) as f:
        schema = yaml.load(f)
    document = format_schema(schema, RSTRenderer())

    with open(output_filename, 'w') as f:
        f.write(document)


if __name__ == '__main__':
    main()
