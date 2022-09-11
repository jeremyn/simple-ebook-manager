"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.csv.

"""
import csv
import shutil
from pathlib import Path

from src.command import Args, Command
from src.csv import get_cmd
from src.util import (
    LOG_LEVEL,
    cmp,
    get_csv_fn,
    get_log_records,
    get_schema_fn,
    write_csv,
)
from tests.base import (
    EXAMPLE_LIBRARY_DIR,
    PLACEHOLDER_DIR_STR,
    UTF_8,
    VALID_CSV_NO_SPLIT_DIR,
    VALID_CSV_SPLIT_DIR,
)
from tests.test_command import CommandTestCase


def _write_localized_valid_csv(orig_csv: Path, valid_csv: Path, new_path: Path) -> None:
    """Write orig_csv to valid_csv and update PLACEHOLDER_DIR_STR to new_path."""
    with orig_csv.open(mode="r+", encoding=UTF_8, newline="") as orig_file:
        rows = list(csv.DictReader(orig_file))

    files_name = str(get_csv_fn(None, "book_files"))
    for row in rows:
        if orig_csv.name in (str(get_csv_fn(None)), files_name):
            row["metadata_directory"] = str(
                new_path
                / Path(row["metadata_directory"]).relative_to(PLACEHOLDER_DIR_STR)
            )
            if orig_csv.name == files_name:
                row["file_full_path"] = str(
                    new_path
                    / Path(row["file_full_path"]).relative_to(PLACEHOLDER_DIR_STR)
                )
    write_csv(valid_csv, rows)


class TestCsv(CommandTestCase):
    """Test the command."""

    CMD: Command

    @classmethod
    def setUpClass(cls) -> None:
        cls.CMD = get_cmd()
        super().setUpClass()

    def _assert_csvs_match(self, valid_fn: Path, test_fn: Path) -> None:
        """Check that two CSV files are equal."""
        with test_fn.open(encoding=UTF_8, newline="") as test_file:
            test_rows = list(csv.reader(test_file))
            self.assertTrue(test_rows)

        with valid_fn.open(encoding=UTF_8, newline="") as valid_file:
            valid_rows = list(csv.reader(valid_file))

        # testing the rows separately is redundant but can help debugging
        self.assertSequenceEqual(valid_rows, test_rows)
        self.assertTrue(cmp(valid_fn, test_fn))

    def test_split_true(self) -> None:
        """Test csv command with split output."""
        o_dir = self.t_dir / "o_dir"
        o_dir.mkdir()
        test_fns = [
            get_csv_fn(o_dir),
            get_csv_fn(o_dir, "authors"),
            get_csv_fn(o_dir, "book_files"),
        ]
        test_fns[0].touch()
        test_fns[1].touch()

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.DIR_VARS.opt, "name1", ".", Args.DIR_VARS.opt, "name2", "."]
                + [Args.LIBRARY_DIRS.opt]
                + [str(l_dir) for l_dir in self.l_dirs]
                + [Args.OUTPUT_DIR.opt, str(o_dir)]
                + [Args.SPLIT.opt]
            )

        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(self.l_dirs[0])}'.",
                "Collecting book data and assigning integer keys.",
                f"Overwriting existing CSV file '{test_fns[0]}'.",
                "Wrote 4 books to file.",
                f"Overwriting existing CSV file '{test_fns[1]}'.",
                f"Creating '{test_fns[2]}'.",
                "Finished writing 3 CSV files.",
            ],
            get_log_records(cm),
        )
        self.assertSequenceEqual(sorted(test_fns), sorted(o_dir.iterdir()))

        for test_fn in test_fns:
            valid_fn = self.t_dir / test_fn.name
            _write_localized_valid_csv(
                get_csv_fn(VALID_CSV_SPLIT_DIR, valid_fn.stem), valid_fn, self.l_dirs[0]
            )
            self._assert_csvs_match(valid_fn, test_fn)

    def test_split_false(self) -> None:
        """Test csv command with non-split output."""
        o_dir = self.t_dir / "test_fn_dir"
        o_dir.mkdir()

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.DIR_VARS.opt, "name1", ".", Args.DIR_VARS.opt, "name2", "."]
                + [Args.LIBRARY_DIRS.opt]
                + [str(l_dir) for l_dir in self.l_dirs]
                + [Args.OUTPUT_DIR.opt, str(o_dir)]
            )

        test_fn = get_csv_fn(o_dir)
        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(self.l_dirs[0])}'.",
                "Collecting book data and assigning integer keys.",
                f"Creating '{test_fn}'.",
                "Wrote 4 books to file.",
                "Finished writing CSV file.",
            ],
            get_log_records(cm),
        )
        self.assertSequenceEqual([test_fn], list(o_dir.iterdir()))

        valid_fn = self.t_dir / test_fn.name
        _write_localized_valid_csv(
            get_csv_fn(VALID_CSV_NO_SPLIT_DIR), valid_fn, self.l_dirs[0]
        )
        self._assert_csvs_match(valid_fn, test_fn)

    def test_quickstart_split_true(self) -> None:
        """Test the quickstart example with split output."""
        l_dir = self.t_dir / "example_library_dir"
        shutil.copytree(EXAMPLE_LIBRARY_DIR, l_dir)

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.LIBRARY_DIRS.opt, str(l_dir)]
                + [Args.OUTPUT_DIR.opt, str(self.t_dir)]
                + [Args.SPLIT.opt]
            )
        csv_fns = [
            self.t_dir / "books.csv",
            self.t_dir / "authors.csv",
            self.t_dir / "book_files.csv",
        ]
        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(l_dir)}'.",
                "Collecting book data and assigning integer keys.",
                f"Creating '{csv_fns[0]}'.",
                "Wrote 2 books to file.",
                f"Creating '{csv_fns[1]}'.",
                f"Creating '{csv_fns[2]}'.",
                "Finished writing 3 CSV files.",
            ],
            get_log_records(cm),
        )
        with csv_fns[0].open(encoding=UTF_8, newline="") as file:
            self.assertEqual(3, len(list(csv.reader(file))))
        with csv_fns[1].open(encoding=UTF_8, newline="") as file:
            self.assertEqual(3, len(list(csv.reader(file))))
        with csv_fns[2].open(encoding=UTF_8, newline="") as file:
            self.assertEqual(5, len(list(csv.reader(file))))

    def test_quickstart_split_false(self) -> None:
        """Test the quickstart example with non-split output."""
        l_dir = self.t_dir / "example_library_dir"
        shutil.copytree(EXAMPLE_LIBRARY_DIR, l_dir)

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.LIBRARY_DIRS.opt, str(l_dir)]
                + [Args.OUTPUT_DIR.opt, str(self.t_dir)]
            )
        csv_fn = self.t_dir / "books.csv"
        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(l_dir)}'.",
                "Collecting book data and assigning integer keys.",
                f"Creating '{csv_fn}'.",
                "Wrote 2 books to file.",
                "Finished writing CSV file.",
            ],
            get_log_records(cm),
        )
        with csv_fn.open(encoding=UTF_8, newline="") as file:
            self.assertEqual(3, len(list(csv.reader(file))))

    def test_combos(self) -> None:
        """Test that the command runs without error, don't check output."""
        self._run_arg_combos(
            [
                [[Args.DIR_VARS.opt, "name1", ".", Args.DIR_VARS.opt, "name2", "."]],
                [[Args.LIBRARY_DIRS.opt] + [str(l_dir) for l_dir in self.l_dirs]],
                [[Args.OUTPUT_DIR.opt, str(self.l_dirs[0])], []],
                [[Args.SPLIT.opt], []],
                [[Args.SCHEMA.opt, str(get_schema_fn(self.l_dirs[0]))], []],
                [[Args.USE_UUID_KEY.opt], []],
            ]
        )

        # check short_opts
        self._run_cmd_main(
            [
                Args.DIR_VARS.short_opt,
                "name1",
                ".",
                Args.DIR_VARS.short_opt,
                "name2",
                ".",
            ]
            + [Args.LIBRARY_DIRS.short_opt]
            + [str(l_dir) for l_dir in self.l_dirs]
            + [Args.OUTPUT_DIR.short_opt, str(self.l_dirs[0])]
            + [Args.SCHEMA.short_opt, str(get_schema_fn(self.l_dirs[0]))]
        )

    def test_error_extra_arg(self) -> None:
        """Test that the command errors with an extra arg."""
        self._test_error_extra_arg([Args.LIBRARY_DIRS.opt, str(self.l_dirs[0])])
