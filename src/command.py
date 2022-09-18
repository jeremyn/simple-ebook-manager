"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Command class and helpers.

"""
from argparse import Action, ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol, Sequence

from src.util import (
    DirVar,
    Newline,
    SimpleEbookManagerException,
    SimpleEbookManagerExit,
)


class DirVarsAction(Action):
    """Argparse action to handle dir vars."""

    def __call__(
        self,
        _: ArgumentParser,
        args: Namespace,
        vals: Optional[str | Sequence[str]],
        opt: Optional[str] = None,
    ) -> None:
        """Append pairs of dir vars and check for duplicates."""
        items = getattr(args, self.dest, None)
        dir_vars: list[DirVar] = [] if items is None else list(items)

        # from the Action docstring: "values" is None or str only if nargs is "?",
        # which it should not be
        if (vals is None) or isinstance(vals, str):
            raise SimpleEbookManagerException(f"problem with '{opt}' values")

        new_dir_var = DirVar(*vals)
        if new_dir_var.name in [dir_var.name for dir_var in dir_vars]:
            raise SimpleEbookManagerExit(
                f"ERROR: duplicate dir var name found: '{new_dir_var.name}'."
            )

        dir_vars.append(new_dir_var)
        setattr(args, self.dest, tuple(dir_vars))


class LibraryDirsAction(Action):
    """Argparse action to handle library dirs."""

    def __call__(
        self,
        _: ArgumentParser,
        args: Namespace,
        vals: Optional[str | Sequence[str]],
        opt: Optional[str] = None,
    ) -> None:
        """Append library dirs as Paths and check for duplicates."""
        items = getattr(args, self.dest, None)
        l_dirs = [] if items is None else list(items)

        # from the Action docstring: "values" is None or str only if nargs is "?",
        # which it should not be
        if (vals is None) or isinstance(vals, str):
            raise SimpleEbookManagerException(f"problem with '{opt}' values")

        for val in vals:
            if not (new_l_dir := Path(val)).is_dir():
                raise SimpleEbookManagerExit(
                    f"ERROR: library dir '{new_l_dir}' is not a directory.",
                )

            if new_l_dir in l_dirs:
                raise SimpleEbookManagerExit(
                    f"ERROR: duplicate library dir found: '{str(new_l_dir)}'."
                )

            l_dirs.append(new_l_dir)

        setattr(args, self.dest, tuple(l_dirs))


@dataclass(frozen=True)
class _Arg:
    opt: str
    kwargs: dict[str, Any]
    short_opt: Optional[str] = None


@dataclass(frozen=True)
class _ArgShortOpt(_Arg):
    short_opt: str


# pylint: disable=invalid-name,too-many-instance-attributes
@dataclass(frozen=True)
class _Args:
    CASE_TO: _Arg = _Arg(opt="--case-to", kwargs={})
    # reserve "cmd" for subcommand delegation
    CMD: _Arg = _Arg(opt="--cmd", kwargs={})
    DIR_VARS: _ArgShortOpt = _ArgShortOpt(
        short_opt="-d",
        opt="--dir-vars",
        kwargs={
            "action": DirVarsAction,
            "default": (),
            "help": "book file directory substitution variables, can be used more than once",
            "metavar": ("VAR_NAME", "VAR_VALUE"),
            "nargs": 2,
        },
    )
    # reserve "help" for standard --help argparse option
    HELP: _ArgShortOpt = _ArgShortOpt(short_opt="-h", opt="--help", kwargs={})
    LIBRARY_DIRS: _ArgShortOpt = _ArgShortOpt(
        short_opt="-l",
        opt="--library-dirs",
        kwargs={
            "action": LibraryDirsAction,
            "help": "one or more directories containing book directories to process",
            "nargs": "+",
            "required": True,
        },
    )
    NEWLINE: _Arg = _Arg(
        opt="--newline",
        kwargs={
            "choices": [e.name.lower() for e in Newline],
            "help": "newline character (defaults to autodetect from library)",
        },
    )
    OUTPUT_DIR: _ArgShortOpt = _ArgShortOpt(
        short_opt="-o",
        opt="--output-dir",
        kwargs={
            "help": "output directory (defaults to first library dir)",
            "type": Path,
        },
    )
    REPLACE_UNICODE: _Arg = _Arg(
        opt="--replace-unicode",
        kwargs={
            "action": "store_true",
            "help": (
                "replace certain Unicode symbols in non-inline string text files with ASCII "
                "equivalents"
            ),
        },
    )
    SCHEMA: _ArgShortOpt = _ArgShortOpt(
        short_opt="-s",
        opt="--schema",
        kwargs={
            "help": "path to schema file (defaults to checking library dirs)",
            "metavar": "SCHEMA_JSON",
            "type": Path,
        },
    )
    SPLIT: _Arg = _Arg(
        opt="--split",
        kwargs={
            "action": "store_true",
            "help": (
                "create multiple CSVs with cross-references to use with spreadsheet software, "
                "otherwise put all data into one CSV file"
            ),
        },
    )
    UPDATE_HASH: _Arg = _Arg(
        opt="--update-hash",
        kwargs={
            "choices": ["autodetect", "md5", "sha256"],
            "const": "autodetect",
            "nargs": "?",
            "help": (
                "update file hashes. Omit entirely to disable hash checking, leave blank or choose "
                '"autodetect" to autodetect from library, or specify "md5" or "sha256" to use that '
                "algorithm."
            ),
        },
    )
    USE_UUID_KEY: _Arg = _Arg(
        opt="--use-uuid-key",
        kwargs={
            "action": "store_true",
            "help": "use UUID4 primary keys, otherwise use integers",
        },
    )
    USER_MODULE: _Arg = _Arg(
        opt="--user-module",
        kwargs={
            "help": "user Python file with custom `process` function",
            "required": True,
            "type": Path,
        },
    )
    USER_SQL_FILE: _Arg = _Arg(
        opt="--user-sql-file",
        kwargs={"help": "user SQL file to run after creating database", "type": Path},
    )


@dataclass(frozen=True)
class _CmdNames:
    CLEAN: str = "clean"
    CSV: str = "csv"
    CUSTOM: str = "custom"
    DB: str = "db"
    # reserve "testing" for testing
    TESTING: str = "testing"


# pylint: enable=invalid-name,too-many-instance-attributes


Args = _Args()
CmdNames = _CmdNames()


# pylint: disable-next=too-few-public-methods
class _MainFunc(Protocol):
    def __call__(
        self, __known_args: Namespace, __extra_args: Optional[list[str]] = None
    ) -> None:
        ...


@dataclass(frozen=True)
class Command:
    """Base class for commands."""

    args: Sequence[_Arg]
    cmd_name: str
    has_extra_args: bool
    main: _MainFunc
    subparser_kwargs: dict[str, str]

    def configure_subparser(self, subparser: ArgumentParser) -> None:
        """Configure argparse subparser."""
        for arg in self.args:
            opts = [arg.opt]
            if arg.short_opt is not None:
                opts.insert(0, arg.short_opt)
            subparser.add_argument(*opts, **arg.kwargs)


def run_cmd_main(sys_argv: Sequence[str], cmds_seq: Sequence[Command]) -> None:
    """Run the correct main function for given input args.

    The general strategy for subcommands comes from:
    https://docs.python.org/3/library/argparse.html#sub-commands

    """
    cmds = {cmd.cmd_name: cmd for cmd in cmds_seq}

    parser = ArgumentParser(prog=sys_argv[0])
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)
    cmd_arg_name = Args.CMD.opt.strip("-")
    for cmd in cmds.values():
        subparser = subparsers.add_parser(cmd.cmd_name, **cmd.subparser_kwargs)
        cmd.configure_subparser(subparser)
        subparser.set_defaults(**{cmd_arg_name: cmd})

    use_parse_known_args = (
        (len(sys_argv) > 1)
        and (sys_argv[1] in cmds)
        and (cmds[sys_argv[1]].has_extra_args)
    )
    known_args, extra_args = (
        parser.parse_known_args(sys_argv[1:])
        if use_parse_known_args
        else (parser.parse_args(sys_argv[1:]), None)
    )

    getattr(known_args, cmd_arg_name).main(known_args, extra_args)
