import argparse

import yaml


class TextBlock(object):
    def __init__(self, text, tab_replacement='  '):
        """

        :type text: str
        """
        self.text = text.replace('\t', tab_replacement)
        self.lines = self.text.splitlines()
        self.width = max([len(line) for line in self.lines])
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


class RSTFormatter(object):

    @staticmethod
    def any_of(blocks):
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
        top_bar = '+{}+'.format('-' * (width-2))
        header_bar = '+{}+'.format('+'.join(['=' * c.padded_width for c in blocks]))
        bottom_bar = '+{}+'.format('+'.join(['-' * c.padded_width for c in blocks]))

        header = '|{}|'.format(HEADER.center(width-2))
        body = '\n'.join(['| {} |'.format(' | '.join([c.get_line_justified(i) for c in blocks])) for i in range(height)])
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


def make_doc(schema, formatter):

    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('schema', help='Path to schema file')
    schema_path = parser.parse_args().schema
    with open(schema_path) as f:
        schema = yaml.load(f)
    document = make_doc(schema, RSTFormatter)


if __name__ == '__main__':
    main()