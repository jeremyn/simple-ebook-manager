"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.command.

"""
import contextlib
import io
import itertools
import shutil
from argparse import ArgumentParser, Namespace
from dataclasses import asdict
from typing import Sequence

from src.command import (
    Args,
    CmdNames,
    Command,
    DirVarsAction,
    LibraryDirsAction,
    run_cmd_main,
)
from src.util import (
    DirVar,
    SimpleEbookManagerException,
    SimpleEbookManagerExit,
    read_schema,
)
from tests.base import VALID_LIBRARY_DIR, SimpleEbookManagerTestCase


class TestArgs(SimpleEbookManagerTestCase):
    """Test Args."""

    def test_no_duplicates(self) -> None:
        """Test Args for duplicate opts."""
        opts = []
        short_opts = []
        for arg in asdict(Args).values():
            opts.append(arg["opt"])
            if (short_opt := arg["short_opt"]) is not None:
                short_opts.append(short_opt)
        self.assertEqual(len(set(opts)), len(opts))
        self.assertEqual(len(set(short_opts)), len(short_opts))


class TestDirVarsAction(SimpleEbookManagerTestCase):
    """Test DirVarsAction."""

    def setUp(self) -> None:
        self.args = Namespace()
        self.dest = "dest"
        self.opt = Args.DIR_VARS.opt
        self.parser = ArgumentParser()
        super().setUp()

    def test_valid(self) -> None:
        """Test with valid input."""
        action = DirVarsAction([self.opt], self.dest)
        dir_vars = [DirVar("a", "b")]

        action(
            self.parser, self.args, [dir_vars[-1].name, dir_vars[-1].value], self.opt
        )
        self.assertSequenceEqual(dir_vars, getattr(self.args, self.dest))

        dir_vars.append(DirVar("c", "d"))
        action(
            self.parser, self.args, [dir_vars[-1].name, dir_vars[-1].value], self.opt
        )
        self.assertSequenceEqual(dir_vars, getattr(self.args, self.dest))

    def test_error_value_none(self) -> None:
        """Error if something is wrong with input values (None)."""
        action = DirVarsAction([self.opt], self.dest)
        with self.assertRaises(SimpleEbookManagerException) as cm:
            action(self.parser, self.args, None, self.opt)
        self.assertEqual(f"problem with '{self.opt}' values", str(cm.exception))

    def test_error_duplicate_name(self) -> None:
        """Error when adding a dir var with a duplicate name."""
        action = DirVarsAction([self.opt], self.dest)
        dir_var = DirVar("a", "b")
        action(self.parser, self.args, [dir_var.name, dir_var.value], self.opt)
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            action(
                self.parser, self.args, [dir_var.name, dir_var.value + "x"], self.opt
            )
        self.assertEqual(
            f"ERROR: duplicate dir var name found: '{dir_var.name}'.", str(cm.exception)
        )


class TestLibraryDirsAction(SimpleEbookManagerTestCase):
    """Test LibraryDirsAction."""

    def setUp(self) -> None:
        self.args = Namespace()
        self.dest = "dest"
        self.opt = Args.LIBRARY_DIRS.opt
        self.parser = ArgumentParser()
        super().setUp()

    def test_valid(self) -> None:
        """Test with valid input.

        Also make sure that library dirs are left unsorted.

        """
        t_dir = self.get_t_dir()
        l_dirs = [t_dir / "c", t_dir / "b", t_dir / "a"]
        for l_dir in l_dirs:
            l_dir.mkdir()

        action = LibraryDirsAction([self.opt], self.dest)
        action(self.parser, self.args, [str(l_dirs[0])], self.opt)
        self.assertSequenceEqual(l_dirs[:1], getattr(self.args, self.dest))

        action(self.parser, self.args, [str(l_dirs[1]), str(l_dirs[2])], self.opt)
        self.assertSequenceEqual(l_dirs, getattr(self.args, self.dest))

    def test_error_value_none(self) -> None:
        """Error if something is wrong with input values (None)."""
        action = LibraryDirsAction([self.opt], self.dest)
        with self.assertRaises(SimpleEbookManagerException) as cm:
            action(self.parser, self.args, None, self.opt)
        self.assertEqual(f"problem with '{self.opt}' values", str(cm.exception))

    def test_error_duplicates(self) -> None:
        """Error if there are duplicate library dirs."""
        t_dir = self.get_t_dir()
        action = LibraryDirsAction([self.opt], self.dest)
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            action(self.parser, self.args, [str(t_dir)] * 2, self.opt)
        self.assertEqual(
            f"ERROR: duplicate library dir found: '{t_dir}'.", str(cm.exception)
        )

    def test_error_not_a_dir(self) -> None:
        """Error if an input library dir is not a directory."""
        action = LibraryDirsAction([self.opt], self.dest)
        not_a_dir_str = str(self.get_t_dir() / "a")
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            action(self.parser, self.args, [not_a_dir_str], self.opt)
        self.assertEqual(
            f"ERROR: library dir '{not_a_dir_str}' is not a directory.",
            str(cm.exception),
        )


# this value is never checked
_ENTRYPOINT_NAME = "ebooks_entrypoint"


class CommandTestCase(SimpleEbookManagerTestCase):
    """Base class for Command tests."""

    CMD: Command

    def setUp(self) -> None:
        self.CMD.configure_subparser(ArgumentParser())
        self.t_dir = self.get_t_dir()
        self.l_dirs = [self.t_dir / "valid_library_dir_copy", self.t_dir / "empty"]
        shutil.copytree(VALID_LIBRARY_DIR, self.l_dirs[0])
        self.l_dirs[1].mkdir()
        self.schema = read_schema(dirs=self.l_dirs)
        super().setUp()

    def _run_arg_combos(self, arg_combos: Sequence[list[list[str]]]) -> None:
        """Run cmd main with arg combinations."""
        for arg_combo in itertools.product(*arg_combos):
            self._run_cmd_main(list(itertools.chain.from_iterable(arg_combo)))

    def _run_cmd_main(self, args: list[str]) -> None:
        """Run cmd main with a single set of args."""
        run_cmd_main([_ENTRYPOINT_NAME, self.CMD.cmd_name] + args, [self.CMD])

    def _test_error_extra_arg(self, args: list[str]) -> None:
        """Test that this command errors with an extra arg."""
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as cm,
        ):
            self._run_cmd_main(args + [Args.CASE_TO.opt])
        self.assertEqual(2, cm.exception.code)


class TestRunCmdMain(SimpleEbookManagerTestCase):
    """Test run_cmd_main without a valid command."""

    def test_main_no_args(self) -> None:
        """Test with no args."""
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as cm,
        ):
            run_cmd_main([_ENTRYPOINT_NAME], [])
        self.assertEqual(2, cm.exception.code)

    def test_main_invalid_command(self) -> None:
        """Test with an invalid command."""
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as cm,
        ):
            run_cmd_main([_ENTRYPOINT_NAME, CmdNames.TESTING], [])
        self.assertEqual(2, cm.exception.code)

    def test_main_help(self) -> None:
        """Test with only --help."""
        with (
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as cm,
        ):
            run_cmd_main([_ENTRYPOINT_NAME, Args.HELP.opt], [])
        self.assertEqual(0, cm.exception.code)
