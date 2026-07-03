import sys
from argparse import ArgumentParser
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import build_parser


class TestCLIParser:
    def test_parser_has_all_subcommands(self):
        parser = build_parser()
        subcommands = {a.dest for a in parser._actions if hasattr(a, 'choices') and a.choices}
        if subcommands:
            choices = set()
            for a in parser._actions:
                if hasattr(a, 'choices') and a.choices:
                    choices.update(a.choices.keys())
            assert choices == {'index', 'reindex', 'clear', 'query', 'info'}

    def test_index_subcommand_defaults(self):
        parser = build_parser()
        args = parser.parse_args(['index'])
        assert args.command == 'index'
        assert args.dirs is None
        assert args.files is None
        assert args.append is False
        assert args.chunk_size == 1000
        assert args.chunk_overlap == 100

    def test_index_subcommand_short_flags(self):
        parser = build_parser()
        args = parser.parse_args(['index', '-d', 'mydir', '-f', 'doc.pdf', '-a'])
        assert args.dirs == ['mydir']
        assert args.files == ['doc.pdf']
        assert args.append is True

    def test_index_multiple_dirs_and_files(self):
        parser = build_parser()
        args = parser.parse_args(['index', '-d', 'd1', '-d', 'd2', '-f', 'a.pdf', '-f', 'b.pdf'])
        assert args.dirs == ['d1', 'd2']
        assert args.files == ['a.pdf', 'b.pdf']

    def test_index_custom_chunk_params(self):
        parser = build_parser()
        args = parser.parse_args(['index', '--chunk-size', '500', '--chunk-overlap', '50'])
        assert args.chunk_size == 500
        assert args.chunk_overlap == 50

    def test_index_long_flags(self):
        parser = build_parser()
        args = parser.parse_args(['index', '--dir', 'mydir', '--file', 'doc.pdf', '--append'])
        assert args.dirs == ['mydir']
        assert args.files == ['doc.pdf']
        assert args.append is True

    def test_reindex_defaults(self):
        parser = build_parser()
        args = parser.parse_args(['reindex'])
        assert args.command == 'reindex'
        assert args.dirs is None
        assert args.files is None
        assert args.chunk_size == 1000
        assert args.chunk_overlap == 100

    def test_reindex_with_flags(self):
        parser = build_parser()
        args = parser.parse_args(['reindex', '-d', 'mydir', '-f', 'doc.pdf'])
        assert args.dirs == ['mydir']
        assert args.files == ['doc.pdf']

    def test_query_defaults(self):
        parser = build_parser()
        args = parser.parse_args(['query'])
        assert args.command == 'query'
        assert args.top_k == 5

    def test_query_custom_top_k(self):
        parser = build_parser()
        args = parser.parse_args(['query', '--top-k', '10'])
        assert args.top_k == 10

    def test_clear_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(['clear'])
        assert args.command == 'clear'

    def test_info_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(['info'])
        assert args.command == 'info'

    def test_no_args_returns_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.command is None
