
import pytest

from ragframework.cli import build_parser


class TestCLIParser:
    def test_parser_has_all_subcommands(self):
        parser = build_parser()
        subcommands = {a.dest for a in parser._actions if hasattr(a, 'choices') and a.choices}
        if subcommands:
            choices = set()
            for a in parser._actions:
                if hasattr(a, 'choices') and a.choices:
                    choices.update(a.choices.keys())
            assert choices == {'index', 'clear', 'query', 'info', 'serve', 'worker'}

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

    def test_query_defaults(self):
        parser = build_parser()
        args = parser.parse_args(['query'])
        assert args.command == 'query'

    def test_clear_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(['clear'])
        assert args.command == 'clear'

    def test_info_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(['info'])
        assert args.command == 'info'

    def test_serve_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(['serve'])
        assert args.command == 'serve'

    def test_worker_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(['worker'])
        assert args.command == 'worker'

    def test_no_args_exits(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])
