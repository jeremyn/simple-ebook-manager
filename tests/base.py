"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Base items for testing.

"""
import shutil
import unittest
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir, mkdtemp

UTF_8 = "utf-8"

_TEST_FILES_DIR = (Path("tests") / "files").resolve()
_VALID_RESULTS_DIR = _TEST_FILES_DIR / "valid_results"

EXAMPLE_LIBRARY_DIR = _TEST_FILES_DIR / "example_library_dir"

VALID_LIBRARY_DIR = _TEST_FILES_DIR / "test_library_dir"
VALID_CSV_NO_SPLIT_DIR = _VALID_RESULTS_DIR / "csv_no_split"
VALID_CSV_SPLIT_DIR = _VALID_RESULTS_DIR / "csv_split"
VALID_DB_SQL_FN = _VALID_RESULTS_DIR / "db" / "books.sql"
VALID_SCHEMA_FN = VALID_LIBRARY_DIR / "schema.json"

_USER_FILES_DIR = _TEST_FILES_DIR / "user_files"
USER_MODULE_FN = _USER_FILES_DIR / "example_user_module.py"
USER_SQL_FN = _USER_FILES_DIR / "db_user_sql_file.sql"

PLACEHOLDER_DIR_STR = "/placeholder_library_dir"


@dataclass(frozen=True)
class ValidBookDirs:
    """Collection of Book test cases."""

    COMPLETE = VALID_LIBRARY_DIR / "Complete Example"
    COMPRESSED_FIELDS = VALID_LIBRARY_DIR / "Compressed Fields Example"
    MINIMAL = VALID_LIBRARY_DIR / "Minimal Example"
    OVERLAP = VALID_LIBRARY_DIR / "Overlap Example"


_UNICODE_ASCII_PAIRS = (
    ("a — a", "a -- a"),
    ("“", '"'),
    ("”", '"'),
    ("‘", "'"),
    ("’", "'"),
    ("…", "..."),
    ("•", "*"),
    # en dash
    ("–", "-"),
    # em dash
    ("—", "--"),
)

UNICODE_LINE, ASCII_LINE = [
    "".join(col) * 2 for col in list(zip(*_UNICODE_ASCII_PAIRS))
]


# exiting a debugger can leave temp dirs, using a prefix keeps them in one place
_TEST_DIR_PREFIX = Path(gettempdir()) / "simple_ebook_manager_test_cases"
_TEST_DIR_PREFIX.mkdir(exist_ok=True)


class SimpleEbookManagerTestCase(unittest.TestCase):
    """Base class for tests."""

    _t_dirs: list[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls._t_dirs = []

    @classmethod
    def tearDownClass(cls) -> None:
        for t_dir in cls._t_dirs:
            shutil.rmtree(t_dir)

    @classmethod
    def get_t_dir(cls) -> Path:
        """Get a temporary directory that will be cleaned up later."""
        t_dir = Path(mkdtemp(dir=_TEST_DIR_PREFIX))
        cls._t_dirs.append(t_dir)
        return t_dir
