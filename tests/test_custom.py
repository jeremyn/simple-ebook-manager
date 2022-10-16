"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.custom.

"""
import shutil
from pathlib import Path
from typing import Sequence
from unittest.mock import MagicMock, patch

from src.all_metadata import get_all_book_dirs
from src.command import Args, Command
from src.custom import IOFuncs, get_cmd
from src.util import LOG_LEVEL, get_log_records, get_string_fn, read_metadata, read_text
from tests.base import EXAMPLE_LIBRARY_DIR, USER_MODULE_FN
from tests.test_command import CommandTestCase

_FIELDNAME = "example_user_module_str_func_name"


class TestCommand(CommandTestCase):
    """Test the command."""

    CMD: Command

    @classmethod
    def setUpClass(cls) -> None:
        cls.CMD = get_cmd()
        super().setUpClass()

    @patch("src.custom.get_process_func")
    def test_mock(self, get_process_func_mock: MagicMock) -> None:
        """Test signature to process function."""
        extra_args = [Args.CASE_TO.opt, "a"]
        self._run_cmd_main(
            [Args.LIBRARY_DIRS.opt]
            + [str(l_dir) for l_dir in self.l_dirs]
            + extra_args
            + [Args.USER_MODULE.opt, str(USER_MODULE_FN)]
        )
        get_process_func_mock.assert_called_once_with(USER_MODULE_FN)
        get_process_func_mock.return_value.assert_called_once_with(
            get_all_book_dirs(self.l_dirs), extra_args, IOFuncs
        )

    def _test_no_mock(
        self, l_dirs: Sequence[Path], user_module_fn: Path, str_func_name: str
    ) -> None:
        """General method to test the command without mocks."""
        b_dirs = get_all_book_dirs(l_dirs)
        valid_msgs = []
        for b_dir in b_dirs:
            valid_msgs.append(f"Processing '{b_dir}'.")
        valid_msgs.append(f"Modified {len(b_dirs)} books.")

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.LIBRARY_DIRS.opt]
                + [str(l_dir) for l_dir in l_dirs]
                + [Args.CASE_TO.opt, str_func_name]
                + [Args.USER_MODULE.opt, str(user_module_fn)]
            )

        self.assertSequenceEqual(valid_msgs, get_log_records(cm))
        for b_dir in b_dirs:
            self.assertEqual(str_func_name, read_metadata(b_dir)[_FIELDNAME])

            desc_fn = get_string_fn(b_dir, "description")
            if not desc_fn.is_file():
                continue
            desc_text = read_text(desc_fn)
            desc_lines = desc_text.split("\n")
            self.assertEqual(
                "\n".join(
                    desc_lines[:2]
                    + [getattr(str, str_func_name)(line) for line in desc_lines[2:]]
                ),
                desc_text,
            )

        # rerunning should not change anything
        valid_msgs[-1] = "Modified 0 books."
        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.LIBRARY_DIRS.short_opt]
                + [str(l_dir) for l_dir in l_dirs]
                + [Args.CASE_TO.opt, str_func_name]
                + [Args.USER_MODULE.opt, str(USER_MODULE_FN)]
            )
        self.assertSequenceEqual(valid_msgs, get_log_records(cm))

    def test_no_mock_lower(self) -> None:
        """Test the command with argument 'lower'."""
        self._test_no_mock(self.l_dirs, USER_MODULE_FN, "lower")

    def test_no_mock_upper(self) -> None:
        """Test the command with argument 'upper'."""
        self._test_no_mock(self.l_dirs, USER_MODULE_FN, "upper")

    def test_quickstart(self) -> None:
        """Test the quickstart example."""
        l_dir = self.t_dir / "example_library_dir"
        shutil.copytree(EXAMPLE_LIBRARY_DIR, l_dir)
        new_user_module_fn = self.t_dir / "my_code.py"
        shutil.copy(USER_MODULE_FN, new_user_module_fn)

        self._test_no_mock([l_dir], new_user_module_fn, "lower")

    def test_error_invalid_arg(self) -> None:
        """Test the command with an invalid arg."""
        invalid_str_func_name = "invalid_str_func_name"
        with self.assertRaises(SystemExit) as cm:
            self._run_cmd_main(
                [Args.LIBRARY_DIRS.opt]
                + [str(l_dir) for l_dir in self.l_dirs]
                + [Args.USER_MODULE.opt, str(USER_MODULE_FN)]
                + [Args.CASE_TO.opt, invalid_str_func_name]
            )
        self.assertEqual(
            f"ERROR: usage requires '{Args.CASE_TO.opt} {{lower,upper}}'.",
            str(cm.exception),
        )
