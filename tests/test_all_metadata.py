"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.all_metadata.

"""
import shutil
import uuid
from itertools import chain

from src.all_metadata import AllMetadata, AMFields, KeyType, get_all_book_dirs
from src.book import Book, SortDisplay
from src.util import (
    LOG_LEVEL,
    DirVar,
    SimpleEbookManagerExit,
    get_log_records,
    get_metadata_fn,
    read_json,
    read_schema,
    write_json,
)
from src.util.file import read_metadata
from tests.base import (
    VALID_LIBRARY_DIR,
    VALID_SCHEMA_FN,
    SimpleEbookManagerTestCase,
    ValidBookDirs,
)


class TestGetAllBookDirs(SimpleEbookManagerTestCase):
    """Test get_all_book_dirs."""

    def test_valid(self) -> None:
        """Test with valid input."""
        t_dir = self.get_t_dir()
        # unsorted l_dirs
        l_dirs = [t_dir / "l_dir2", t_dir / "l_dir1"]
        b_dirs = (
            l_dirs[0] / "a",
            l_dirs[0] / "b",
            l_dirs[1] / "a",
            l_dirs[1] / "b",
            l_dirs[1] / ".c",
            l_dirs[1] / "missing",
        )
        for i, b_dir in enumerate(b_dirs):
            b_dir.mkdir(parents=True)
            if i != (len(b_dirs) - 1):
                get_metadata_fn(b_dir).touch()

        self.assertSequenceEqual(b_dirs[:-2], get_all_book_dirs(l_dirs))

    def test_error_library_dir_is_book_dir(self) -> None:
        """Error if one of l_dirs looks like a book dir."""
        b_dir = ValidBookDirs.COMPLETE
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            get_all_book_dirs([b_dir])
        self.assertEqual(
            (
                f"ERROR: specified library dir '{b_dir}' has a '{get_metadata_fn(b_dir).name}' "
                "file and might be a book directory."
            ),
            str(cm.exception),
        )

    def test_error_no_book_dirs_found(self) -> None:
        """Error if no book dirs found."""
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            get_all_book_dirs([self.get_t_dir()])
        self.assertEqual("ERROR: no book directories found.", str(cm.exception))


class TestAllMetadata(SimpleEbookManagerTestCase):
    """Test AllMetadata."""

    def setUp(self) -> None:
        self.dir_vars = (DirVar("name1", "."), DirVar("name2", "."))
        self.schema = read_schema(fn=VALID_SCHEMA_FN)
        valid_books = tuple(
            sorted(
                [
                    Book.from_args(b_dir, self.dir_vars, self.schema)
                    for b_dir in get_all_book_dirs([VALID_LIBRARY_DIR])
                ]
            )
        )
        valid_fields: AMFields = {
            "authors": (
                SortDisplay("Author1, CompleteExample", "CompleteExample Author1", "1"),
                SortDisplay("Author2, CompleteExample", "CompleteExample Author2", "2"),
                SortDisplay(
                    "CompressedFieldsExampleAuthor",
                    "CompressedFieldsExampleAuthor",
                    "3",
                ),
            )
        }
        valid_files = tuple(chain.from_iterable(book.files for book in valid_books))
        self.valid_am = AllMetadata(valid_books, valid_fields, valid_files)
        super().setUp()

    def test_int(self) -> None:
        """Test from_args with key_type INT."""
        with self.assertLogs(level=LOG_LEVEL) as cm:
            am = AllMetadata.from_args(
                [VALID_LIBRARY_DIR], self.dir_vars, self.schema, key_type=KeyType.INT
            )
        self.assertSequenceEqual(
            ["Collecting book data and assigning integer keys."], get_log_records(cm)
        )

        # Replace book sortdisplay fields and title with sortdisplays with keys
        for i, book in enumerate(self.valid_am.books):
            book.title = SortDisplay(book.title.sort, book.title.display, str(i + 1))

            for fieldname, book_sds in book.fields.sortdisplays.items():
                sds_with_keys = []
                for sd in book_sds:
                    for valid_sd in self.valid_am.fields[fieldname]:
                        if (valid_sd.sort, valid_sd.display) == (sd.sort, sd.display):
                            sds_with_keys.append(valid_sd)
                            break
                book.fields.sortdisplays[fieldname] = tuple(sds_with_keys)

        self.assertEqual(self.valid_am, am)

    def test_none(self) -> None:
        """Test from_args with key_type NONE."""
        with self.assertLogs(level=LOG_LEVEL) as cm:
            am = AllMetadata.from_args(
                [VALID_LIBRARY_DIR], self.dir_vars, self.schema, key_type=KeyType.NONE
            )
        self.assertSequenceEqual(["Collecting book data."], get_log_records(cm))
        valid_fields_no_keys: AMFields = {
            "authors": tuple(
                SortDisplay(a.sort, a.display) for a in self.valid_am.fields["authors"]
            )
        }
        self.assertEqual(
            AllMetadata(self.valid_am.books, valid_fields_no_keys, self.valid_am.files),
            am,
        )

    def _assert_valid_uuid(self, sd: SortDisplay) -> None:
        try:
            uuid.UUID(sd.key)
        except ValueError:
            self.fail(f"bad UUID key: {sd}")

    def test_uuid(self) -> None:
        """Test from_args with key_type UUID."""
        with self.assertLogs(level=LOG_LEVEL) as cm:
            am = AllMetadata.from_args(
                [VALID_LIBRARY_DIR], self.dir_vars, self.schema, key_type=KeyType.UUID
            )
        self.assertSequenceEqual(
            ["Collecting book data and assigning UUID keys."], get_log_records(cm)
        )

        # Replace am sortdisplay fields with sortdisplays with keys
        for fieldname, valid_sds in self.valid_am.fields.items():
            sds_with_keys = []
            am_sds = am.fields[fieldname]
            for valid_sd, am_sd in zip(valid_sds, am_sds, strict=True):
                self.assertEqual(valid_sd.sort, am_sd.sort)
                self.assertEqual(valid_sd.display, am_sd.display)
                self._assert_valid_uuid(am_sd)
                sds_with_keys.append(am_sd)
            self.valid_am.fields[fieldname] = tuple(sds_with_keys)

        # Replace book sortdisplay fields and title with sortdisplays with keys
        for book, am_book in zip(self.valid_am.books, am.books, strict=True):
            self.assertEqual(book.title.sort, am_book.title.sort)
            self.assertEqual(book.title.display, am_book.title.display)
            self._assert_valid_uuid(am_book.title)
            book.title = am_book.title

            for fieldname, book_sds in book.fields.sortdisplays.items():
                sds_with_keys = []
                for sd in book_sds:
                    for valid_sd in self.valid_am.fields[fieldname]:
                        if (valid_sd.sort, valid_sd.display) == (sd.sort, sd.display):
                            sds_with_keys.append(valid_sd)
                            break
                book.fields.sortdisplays[fieldname] = tuple(sds_with_keys)

        self.assertEqual(self.valid_am, am)

    def test_error_duplicate_title(self) -> None:
        """Error if a title is duplicated between books."""
        l_dir = self.get_t_dir()
        b_dirs = [l_dir / "a", l_dir / "b"]
        for b_dir in b_dirs:
            shutil.copytree(ValidBookDirs.MINIMAL, b_dir)

        metadata_fn = get_metadata_fn(b_dirs[1])
        metadata = read_json(metadata_fn)
        fieldname = self.schema.title_fieldname

        # same sort and display
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            AllMetadata.from_args(
                [l_dir], self.dir_vars, self.schema, key_type=KeyType.NONE
            )
        self.assertEqual(
            (
                f"ERROR: the title with sort '{metadata[fieldname]['sort']}' and display "
                f"'{metadata[fieldname]['display']}' appears in more than one book."
            ),
            str(cm.exception),
        )

        # different sort, same display
        orig_sort = metadata[fieldname]["sort"]

        metadata[fieldname]["sort"] += "x"
        write_json(metadata_fn, metadata)

        with self.assertRaises(SimpleEbookManagerExit) as cm:
            AllMetadata.from_args(
                [l_dir], self.dir_vars, self.schema, key_type=KeyType.NONE
            )
        self.assertEqual(
            (
                f"ERROR: the title display value '{metadata[fieldname]['display']}' has more than "
                "one sort value over all books."
            ),
            str(cm.exception),
        )

        # same sort, different display
        metadata[fieldname]["sort"] = orig_sort
        metadata[fieldname]["display"] += "x"
        write_json(metadata_fn, metadata)

        with self.assertRaises(SimpleEbookManagerExit) as cm:
            AllMetadata.from_args(
                [l_dir], self.dir_vars, self.schema, key_type=KeyType.NONE
            )
        self.assertEqual(
            (
                f"ERROR: the title sort value '{metadata[fieldname]['sort']}' has more than one "
                "display value over all books."
            ),
            str(cm.exception),
        )

    def test_error_partial_duplicate_sortdisplay(self) -> None:
        """Error if there are partial duplicate sortdisplays between books."""
        fieldname = "authors"
        l_dir = self.get_t_dir()
        for i, b_dir in enumerate([l_dir / "valid", l_dir / "changed"]):
            shutil.copytree(ValidBookDirs.COMPLETE, b_dir)
            metadata_fn = get_metadata_fn(b_dir)
            metadata = read_metadata(metadata_fn)
            metadata["authors"] = metadata["authors"][0]
            if i == 1:
                # avoid duplicate title error
                metadata["book_title"] = "asdf"

                orig_sort = metadata[fieldname]["sort"]
                metadata[fieldname]["sort"] += "x"
            write_json(metadata_fn, metadata)

        with self.assertRaises(SimpleEbookManagerExit) as cm:
            AllMetadata.from_args(
                [l_dir], self.dir_vars, self.schema, key_type=KeyType.NONE
            )
        self.assertEqual(
            (
                f"ERROR: for field '{fieldname}' the display value "
                f"'{metadata[fieldname]['display']}' has more than one sort value over all books."
            ),
            str(cm.exception),
        )

        # same sort, different display
        metadata[fieldname]["sort"] = orig_sort
        metadata[fieldname]["display"] += "x"
        write_json(metadata_fn, metadata)

        with self.assertRaises(SimpleEbookManagerExit) as cm:
            AllMetadata.from_args(
                [l_dir], self.dir_vars, self.schema, key_type=KeyType.NONE
            )
        self.assertEqual(
            (
                f"ERROR: for field '{fieldname}' the sort value '{metadata[fieldname]['sort']}' "
                "has more than one display value over all books."
            ),
            str(cm.exception),
        )
