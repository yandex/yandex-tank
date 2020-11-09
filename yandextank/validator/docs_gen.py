import argparse

import imp
import yaml
from yaml.scanner import ScannerError

TYPE = 'type'
LIST = 'list'
DESCRIPTION = 'description'
REQUIRED = 'required'
DEFAULT = 'default'
ALLOWED = 'allowed'
VALUES_DSC = 'values_description'
ONE_OF = 'one of'
SCHEMA = 'schema'
EXAMPLES = 'examples'
ANYOF = 'anyof'
NO_DSC = '(no description)'
VALIDATOR = 'validator'

NoneType = type(None)


class TextBlock(object):
    def __init__(self, text, tab_replacement='  ', ending=''):
        """

        :type text: str
        """
        self.text = str(text).replace('\t', tab_replacement)
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
        :return: str
        """
        prepared_content = content.strip().replace('\n', new_line_replacement).replace('\t', tab_replacement)
        return '{}\n{}'.format(prepared_content, '=' * len(prepared_content))

    @staticmethod
    def subtitle(content, new_line_replacement=' ', tab_replacement='  '):
        prepared_content = content.strip().replace('\n', new_line_replacement).replace('\t', tab_replacement)
        return '{}\n{}'.format(prepared_content, '-' * len(prepared_content))

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
    def def_list(items, sort=True, newlines=True):
        def format_value(value):
            if isinstance(value, (int, bool, NoneType)):
                return format_value(str(value))
            if isinstance(value, str):
                return '\n '.join(value.splitlines())
            elif isinstance(value, TextBlock):
                return '\n '.join(value.lines)
            elif isinstance(value, dict):
                return '\n '.join(RSTRenderer.def_list(value, sort, newlines).splitlines())
            elif isinstance(value, list):
                return '\n '.join(RSTRenderer.bullet_list([TextBlock(item) for item in value]).lines)
            else:
                raise ValueError('Unsupported value type: {}\n{}'.format(type(value), value))

        sort = sorted if sort else lambda x: x
        template = '{}\n {}' if newlines else ':{}: {}'
        return '\n' + '\n'.join([template.format(k.replace('\n', ' '),
                                                 format_value(v).strip())
                                 for k, v in sort(items.items())]) if items else ''

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
        return content.replace('-', r'\-')

    del with_escape


def render_body(renderer, option_kwargs, exclude_keys, special_keys=None):
    """

    :type option_kwargs: dict
    :type exclude_keys: list
    :type special_keys: dict
    """
    common_formatters = {
        EXAMPLES: lambda examples: renderer.def_list({renderer.mono(example): annotation for example, annotation in examples.items()})
    }

    def default_fmt(x):
        return x

    special_keys = special_keys or {}
    special_part = '\n'.join([special_handler(renderer, option_kwargs[special_key])
                              for special_key, special_handler in special_keys.items()
                              if special_key in option_kwargs])
    uncommon_keys = set(exclude_keys) | set(special_keys.keys())
    common_part = renderer.field_list({
        k: common_formatters.get(k, default_fmt)(v)
        for k, v in option_kwargs.items()
        if k not in uncommon_keys
    })

    return '\n'.join([_ for _ in [common_part, special_part] if _])


def render_values_description(renderer, option_kwargs):
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
    return renderer.field_list({ONE_OF: values_description})


def allowed(renderer, values):
    return renderer.field_list({ONE_OF: '[{}]'.format(', '.join([renderer.mono(value) for value in values]))},
                               newlines=False)


class OptionFormatter(object):
    def __init__(self, option_schema):
        """

        :type option_schema: dict
        """
        self.option_name, self.option_kwargs = next(iter(option_schema.items()))
        # print(option_name, option_kwargs)
        self.formatter = self.__guess_formatter()

    def format_dsc(self, renderer):
        dsc = self.option_kwargs.get(DESCRIPTION, NO_DSC).strip('. ')
        if DEFAULT in self.option_kwargs:
            default_value = self.option_kwargs.get(DEFAULT)
            if default_value == '':
                default_value = '""'
            return ' '.join([renderer.italic('- {}. Default:'.format(dsc)),
                             renderer.mono(default_value)])
        elif REQUIRED in self.option_kwargs:
            return renderer.italic('- {}.'.format(dsc)) +\
                ' ' +\
                renderer.bold('Required.')
        else:
            return renderer.italic('- {}.'.format(dsc))

    def scalar_formatter(self, renderer, header=True):
        hdr = renderer.subtitle(renderer.mono(self.option_name) + ' ' + '({})'.format(self.option_kwargs.get(TYPE))) \
            if header else ''
        dsc = self.format_dsc(renderer)
        body = render_body(renderer, self.option_kwargs, [VALIDATOR, TYPE, DESCRIPTION, DEFAULT, REQUIRED], {'allowed': allowed})
        return '\n'.join([_ for _ in [hdr, dsc, body] if _])

    def scalar_with_values_description(self, renderer, header=True):
        hdr = renderer.subtitle(renderer.mono(self.option_name) + ' ' + '({})'.format(self.option_kwargs.get(TYPE))) \
            if header else ''
        dsc = self.format_dsc(renderer)
        body = render_body(renderer, self.option_kwargs, [VALIDATOR, TYPE, DESCRIPTION, DEFAULT, REQUIRED, ALLOWED, VALUES_DSC])
        values_description_block = render_values_description(renderer, self.option_kwargs)
        return '\n'.join([_ for _ in [hdr, dsc, body, values_description_block] if _])

    def dict_formatter(self, renderer, header=True):
        hdr = renderer.subtitle(renderer.mono(self.option_name) + ' ' + '({})'.format(self.option_kwargs.get(TYPE))) \
            if header else ''
        dsc = self.format_dsc(renderer)

        dict_schema = self.option_kwargs[SCHEMA]

        schema_block = renderer.field_list({
            '{} ({})'.format(renderer.mono(key), dict_schema[key].get(TYPE, 'anyof')): get_formatter({key: value})(renderer, header=False)
            for key, value in dict_schema.items()})
        body = render_body(renderer, self.option_kwargs, [VALIDATOR, TYPE, DESCRIPTION, DEFAULT, REQUIRED, SCHEMA])
        return '\n'.join([_ for _ in [hdr, dsc, schema_block, body] if _])

    def anyof_formatter(self, renderer, header=True):
        types = [case[TYPE] for case in self.option_kwargs[ANYOF] if TYPE in case]
        hdr = renderer.subtitle(renderer.mono(self.option_name) + ' ' + '({})'.format(' or '.join(types))) \
            if header else ''
        dsc = self.format_dsc(renderer)
        values_description_block = render_values_description(renderer, self.option_kwargs) \
            if VALUES_DSC in self.option_kwargs else ''
        body = render_body(renderer, self.option_kwargs, [VALIDATOR, TYPE, DESCRIPTION, DEFAULT, REQUIRED, ANYOF, VALUES_DSC])

        return '\n'.join([_ for _ in [hdr, dsc, values_description_block, body] if _])

    def list_formatter(self, renderer, header=True):
        schema = self.option_kwargs[SCHEMA]
        hdr = renderer.subtitle(renderer.mono(self.option_name) + ' '
                                + '({} of {})'.format(self.option_kwargs.get(TYPE, LIST), schema.get(TYPE, '')))
        dsc = self.format_dsc(renderer)
        body = render_body(renderer, self.option_kwargs, [VALIDATOR, TYPE, DEFAULT, REQUIRED, DESCRIPTION, SCHEMA])
        if set(schema.keys()) - {TYPE}:
            schema_block = renderer.field_list({
                '[list_element] ({})'.format(schema.get(TYPE, '')):
                    get_formatter({'list_element': schema})(renderer, header=False)
            })
            return '\n'.join([_ for _ in [hdr, dsc, schema_block, body] if _])
        else:
            return '\n'.join([_ for _ in [hdr, dsc, body] if _])

    def __guess_formatter(self):
        if ANYOF in self.option_kwargs:
            return self.anyof_formatter
        elif SCHEMA in self.option_kwargs:
            return self.list_formatter if self.option_kwargs.get(TYPE) == LIST else self.dict_formatter
        elif VALUES_DSC in self.option_kwargs:
            return self.scalar_with_values_description
        else:
            return self.scalar_formatter


def get_formatter(option_schema):
    """

    :type option_schema: dict
    """
    return OptionFormatter(option_schema).formatter


def format_option(option_schema, renderer):
    return get_formatter(option_schema)(renderer)


def format_schema(schema, renderer, title=None):
    """

    :param dict schema: Cerberus config schema
    :type renderer: RSTRenderer
    """
    body = '\n\n'.join(
        sorted([format_option({option_name: option_schema}, renderer) for option_name, option_schema in schema.items()]))

    if title:
        title = renderer.title(title)
        return title + '\n\n' + body
    else:
        return body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('schema', help='Path to schema file')
    parser.add_argument('-o', '--output_filename', default='output.rst', help='Name for the output rst document')
    parser.add_argument('--title', default=None, help='Document title')
    parser.add_argument('-a', '--append', action='store_true', help='Don\'t overwrite output file')
    args = parser.parse_args()

    schema_path = args.schema
    output_filename = args.output_filename
    title = args.title
    append = args.append

    try:
        with open(schema_path) as f:
            schema = yaml.load(f, Loader=yaml.FullLoader)
    except ScannerError:
        schema_module = imp.load_source('schema', schema_path)
        schema = schema_module.OPTIONS
    document = format_schema(schema, RSTRenderer(), title)

    if append:
        with open(output_filename, 'a') as f:
            f.write('\n\n')
            f.write(document)
    else:
        with open(output_filename, 'w') as f:
            f.write(document)


if __name__ == '__main__':
    main()
