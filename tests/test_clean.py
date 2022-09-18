"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.clean.

"""
import shutil
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from src.book import BookFile
from src.clean import _get_algo, get_cmd
from src.command import Args, Command
from src.util import (
    LOG_LEVEL,
    Algorithm,
    SimpleEbookManagerExit,
    cmp,
    get_log_records,
    get_metadata_fn,
    get_schema_fn,
    get_string_fn,
    read_json,
    read_metadata,
    read_text,
    write_json,
    write_text,
)
from tests.base import (
    EXAMPLE_LIBRARY_DIR,
    VALID_LIBRARY_DIR,
    SimpleEbookManagerTestCase,
    ValidBookDirs,
)
from tests.test_command import CommandTestCase


class TestGetAlgo(SimpleEbookManagerTestCase):
    """Test _get_algo."""

    def setUp(self) -> None:
        b_dir = ValidBookDirs.MINIMAL
        metadata = read_metadata(b_dir)
        self.bookfile = BookFile.from_args(
            book_title_sort=metadata["book_title"],
            basename=metadata["book_files"]["name"],
            metadata_dir=b_dir,
            dir_vars=(),
            input_dir_str=metadata["book_files"]["directory"],
            hash_=metadata["book_files"]["hash"],
        )
        super().setUp()

    def test_autodetect(self) -> None:
        """Test algo_str 'autodetect'."""
        self.assertEqual(Algorithm.MD5, _get_algo("autodetect", self.bookfile))

    def test_error_autodetect(self) -> None:
        """Error if autodetect fails."""
        self.bookfile.hash = "bad"
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            _get_algo("autodetect", self.bookfile)
        self.assertEqual(
            (
                f"ERROR: '{Args.UPDATE_HASH.opt}' provided without algorithm and autodetect failed "
                f"on the hash for '{self.bookfile.basename}' in "
                f"'{get_metadata_fn(self.bookfile.metadata_dir)}'."
            ),
            str(cm.exception),
        )

    def test_input_algo(self) -> None:
        """Test algo_str with valid algo."""
        self.assertEqual(Algorithm.SHA256, _get_algo("sha256", self.bookfile))


class TestCommand(CommandTestCase):
    """Test the command."""

    CMD: Command
    DESC_FIELDNAME = "description"

    @classmethod
    def setUpClass(cls) -> None:
        cls.CMD = get_cmd()
        super().setUpClass()

    def _assert_files_match(self, valid_l_dir: Path, test_l_dir: Path) -> None:
        """General method to check that files match."""
        valid_b_dirs = sorted(d for d in valid_l_dir.iterdir() if d.is_dir())
        for valid_b_dir in valid_b_dirs:
            test_b_dir = test_l_dir / valid_b_dir.name
            self.assertTrue(
                cmp(get_metadata_fn(valid_b_dir), get_metadata_fn(test_b_dir))
            )
            valid_desc_fn = get_string_fn(valid_b_dir, self.DESC_FIELDNAME)
            if valid_desc_fn.is_file():
                self.assertTrue(
                    cmp(valid_desc_fn, get_string_fn(test_b_dir, self.DESC_FIELDNAME))
                )

    def test_no_changes(self) -> None:
        """Test command with no changes needed."""
        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.DIR_VARS.opt, "name1", ".", Args.DIR_VARS.opt, "name2", "."]
                + [Args.LIBRARY_DIRS.opt]
                + [str(l_dir) for l_dir in self.l_dirs]
                + [Args.UPDATE_HASH.opt]
            )

        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(self.l_dirs[0])}'.",
                "Collecting book data.",
                "Calculating file hashes.",
                "Done calculating file hashes.",
                "Starting processing.",
                "Processed 4 books.",
                "Finished processing, no changes needed.",
            ],
            get_log_records(cm),
        )
        self._assert_files_match(VALID_LIBRARY_DIR, self.l_dirs[0])

    @patch("src.clean._BATCH_SIZE", 3)
    def test_changes(self) -> None:
        """Test command with changes needed. Also exercises dir vars."""
        # change hashes in metadata file in test_b_dir
        test_b_dir = self.l_dirs[0] / ValidBookDirs.COMPLETE.name
        metadata_fn = get_metadata_fn(test_b_dir)
        metadata = read_json(metadata_fn)
        orig_file_dicts = deepcopy(metadata["book_files"])
        for file_dict in metadata["book_files"]:
            file_dict["hash"] = "bad"
        write_json(metadata_fn, metadata)

        # remove title from desc file in test_b_dir
        desc_fn = get_string_fn(test_b_dir, self.DESC_FIELDNAME)
        write_text(desc_fn, "\n".join(read_text(desc_fn).split("\n")[2:]))

        # move book files from test_b_dir to storage_dir to test dir vars
        storage_dir = self.t_dir / "storage_dir"
        storage_dir.mkdir()
        for file_dict in orig_file_dicts:
            file_name = file_dict["name"]
            shutil.move(test_b_dir / file_name, storage_dir / file_name)

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [
                    Args.DIR_VARS.opt,
                    "name1",
                    str(storage_dir.parent),
                    Args.DIR_VARS.opt,
                    "name2",
                    str(storage_dir.name),
                ]
                + [Args.LIBRARY_DIRS.opt]
                + [str(l_dir) for l_dir in self.l_dirs]
                + [Args.UPDATE_HASH.opt]
            )

        hash_msgs = [
            (
                f"'{storage_dir / d['name']}': hash mismatch: calculated: "
                f"'{d['hash']}', hash in metadata file: 'bad', metadata file: '{metadata_fn}'."
            )
            for d in orig_file_dicts
        ]

        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(self.l_dirs[0])}'.",
                "Collecting book data.",
                "Calculating file hashes.",
                "Done calculating file hashes.",
                "Starting processing.",
                hash_msgs[0],
                hash_msgs[1],
                f"'{metadata_fn}': file changed.",
                f"'{desc_fn}': file changed.",
                "Processed 3 books.",
                "Processed 4 books.",
                "Finished processing, changes made!",
            ],
            get_log_records(cm),
        )
        self._assert_files_match(VALID_LIBRARY_DIR, self.l_dirs[0])

    def test_quickstart(self) -> None:
        """Test the quickstart example."""
        l_dir = self.t_dir / "example_library_dir"
        shutil.copytree(EXAMPLE_LIBRARY_DIR, l_dir)

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.LIBRARY_DIRS.opt, str(l_dir)] + [Args.UPDATE_HASH.opt]
            )
        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(l_dir)}'.",
                "Collecting book data.",
                "Calculating file hashes.",
                "Done calculating file hashes.",
                "Starting processing.",
                "Processed 2 books.",
                "Finished processing, no changes needed.",
            ],
            get_log_records(cm),
        )
        self._assert_files_match(EXAMPLE_LIBRARY_DIR, l_dir)

    def test_combos(self) -> None:
        """Test that the command runs without error, don't check output."""
        self._run_arg_combos(
            [
                [[Args.DIR_VARS.opt, "name1", ".", Args.DIR_VARS.opt, "name2", "."]],
                [[Args.LIBRARY_DIRS.opt] + [str(l_dir) for l_dir in self.l_dirs]],
                [[Args.NEWLINE.opt, "posix"], [Args.NEWLINE.opt, "windows"], []],
                [[Args.REPLACE_UNICODE.opt], []],
                [[Args.SCHEMA.opt, str(get_schema_fn(self.l_dirs[0]))], []],
                [
                    [Args.UPDATE_HASH.opt],
                    [Args.UPDATE_HASH.opt, "md5"],
                    [Args.UPDATE_HASH.opt, "sha256"],
                    [],
                ],
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
            + [Args.SCHEMA.short_opt, str(get_schema_fn(self.l_dirs[0]))]
        )

    def test_error_extra_arg(self) -> None:
        """Test that the command errors with an extra arg."""
        self._test_error_extra_arg([Args.LIBRARY_DIRS.opt, str(self.l_dirs[0])])
