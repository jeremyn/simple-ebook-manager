"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.book.

"""
import platform
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.book import Book, BookFile, SortDisplay
from src.book.book import (
    _BookFields,
    _get_date,
    _get_files,
    _get_keyvalues,
    _get_sortdisplays,
    _get_string,
    _remove_whitespace,
    _replace_unicode,
)
from src.book.date import BookDate
from src.book.keyvalue import BookKeyValue
from src.util import (
    DirVar,
    DirVars,
    Newline,
    Schema,
    SchemaItemTypes,
    SimpleEbookManagerException,
    SimpleEbookManagerExit,
    cmp,
    get_metadata_fn,
    get_string_fn,
    read_metadata,
    read_schema,
    read_text,
    write_json,
    write_text,
)
from tests.base import (
    ASCII_LINE,
    UNICODE_LINE,
    VALID_SCHEMA_FN,
    SimpleEbookManagerTestCase,
    ValidBookDirs,
)


class TestDate(SimpleEbookManagerTestCase):
    """Test BookDate."""

    def setUp(self) -> None:
        # 2000-Jan-31
        self.input_format = "%Y-%b-%d"
        super().setUp()

    def test_year_after_1000(self) -> None:
        """Test with year 1000 or after."""
        bookdate = BookDate.from_args("2000-Jan-31", self.input_format)
        self.assertEqual("2000-Jan-31", bookdate.as_str(self.input_format))
        self.assertEqual("2000-01-31", bookdate.as_str("%Y-%m-%d"))
        self.assertEqual("31-2000-01", bookdate.as_str("%d-%Y-%m"))
        self.assertEqual("01-31-2000", bookdate.as_str("%m-%d-%Y"))

    def test_year_before_1000(self) -> None:
        """Test with year before 1000."""
        # check that https://github.com/python/cpython/issues/57514 is still active
        if platform.uname().system == "Linux":
            self.assertEqual(
                "100-Dec-01", datetime.strftime(datetime(100, 12, 1), self.input_format)
            )

        bookdate = BookDate.from_args("0100-Jan-31", self.input_format)
        self.assertEqual("0100-Jan-31", bookdate.as_str(self.input_format))
        self.assertEqual("0100-01-31", bookdate.as_str("%Y-%m-%d"))
        self.assertEqual("31-0100-01", bookdate.as_str("%d-%Y-%m"))
        self.assertEqual("01-31-0100", bookdate.as_str("%m-%d-%Y"))


class TestGetDate(SimpleEbookManagerTestCase):
    """Test _get_date."""

    def setUp(self) -> None:
        self.input_format = "%Y-%b-%d"
        super().setUp()

    def test_none(self) -> None:
        """Test None input."""
        self.assertIsNone(_get_date(None, self.input_format))

    def test_not_none(self) -> None:
        """Test non-None input."""
        dt_input = "2000-Jan-31"
        self.assertEqual(
            BookDate.from_args(dt_input, self.input_format),
            _get_date(dt_input, self.input_format),
        )


class TestFile(SimpleEbookManagerTestCase):
    """Test BookFile."""

    def setUp(self) -> None:
        self.storage_dir = Path("/tmp/storage_dir").resolve()
        self.file_dict = {"name": "file.txt", "hash": "hash"}
        self.book_title_sort = "test book"
        self.metadata_dir = Path("/tmp/metadata_dir")
        super().setUp()

    def _test_fn(
        self, dir_vars: DirVars, input_dir_str: str, error_msg: Optional[str] = None
    ) -> None:
        """General method to test BookFile fn."""
        args = (
            self.book_title_sort,
            self.file_dict["name"],
            self.metadata_dir,
            dir_vars,
            input_dir_str,
            self.file_dict["hash"],
        )
        if error_msg is None:
            file = BookFile.from_args(*args)
            self.assertEqual((self.storage_dir / file.basename).resolve(), file.fn)
        else:
            with self.assertRaises(SimpleEbookManagerExit) as cm:
                BookFile.from_args(*args)
            self.assertEqual(error_msg, str(cm.exception))

    def test_fn_no_dir_var(self) -> None:
        """Test with no dir vars.

        Input: <no input>
        Test: "/tmp/storage_dir" -> "/tmp/storage_dir"

        """
        self._test_fn((), str(self.storage_dir))

    def test_fn_relative(self) -> None:
        """Test with directory that is relative after interpolation, with multiple variables.

        Input: name1=.. , name2=storage_dir
        Test: "{name1}/{name2}" -> "../storage_dir"

        """
        dir_vars = (DirVar("name1", ".."), DirVar("name2", self.storage_dir.name))
        self._test_fn(dir_vars, f"{{{dir_vars[0].name}}}/{{{dir_vars[1].name}}}")

    def test_fn_absolute(self) -> None:
        """Test with directory that is absolute after interpolation.

        Input: name1=/tmp/storage_dir
        Test: "{name1}" -> "/tmp/storage_dir"

        """
        dir_vars = (DirVar("name1", str(self.storage_dir)),)
        self._test_fn(dir_vars, f"{{{dir_vars[0].name}}}")

    def test_fn_extra_var(self) -> None:
        """Accept an extra variable in dir vars.

        Input: name1=/tmp/storage_dir , name2=value2
        Test: "{name1}" -> "/tmp/storage_dir"

        """
        dir_vars = (DirVar("name1", str(self.storage_dir)), DirVar("name2", "value2"))
        self._test_fn(dir_vars, f"{{{dir_vars[0].name}}}")

    def test_fn_error_missing_var_none_provided(self) -> None:
        """Error if a dir var is required and no dir vars are provided.

        Input: <no input>
        Test: "{name1}" -> error

        """
        input_dir_str = "{name1}"
        self._test_fn(
            (),
            input_dir_str,
            (
                "ERROR: not enough dir_vars provided, metadata file directory: "
                f"'{self.metadata_dir}', file relative directory: '{input_dir_str}', dir_vars: "
                "'<none provided>'."
            ),
        )

    def test_fn_error_missing_var_some_provided(self) -> None:
        """Error if a dir_var is required and some dir vars are provided.

        Input: name1=value1 , name2=value2
        Test: "{name3}" -> error

        """
        dir_vars = (DirVar("name1", "value1"), DirVar("name2", "value2"))
        input_dir_str = "{name3}"
        self._test_fn(
            dir_vars,
            input_dir_str,
            (
                "ERROR: not enough dir_vars provided, metadata file directory: "
                f"'{self.metadata_dir}', file relative directory: '{input_dir_str}', dir_vars: "
                f"'{dir_vars[0]}, {dir_vars[1]}'."
            ),
        )


class TestGetFiles(SimpleEbookManagerTestCase):
    """Test _get_files."""

    def setUp(self) -> None:
        self.file_dicts = sorted(
            [
                {"name": "file1.txt", "hash": "hash1"},
                {"name": "file2.txt", "hash": "hash2"},
            ],
            key=lambda fd: fd["name"],
        )
        self.book_title_sort = "test book"
        self.metadata_dir = Path("metadata_dir")
        self.dir_vars = (DirVar("a", "b"), DirVar("c", "d"))

        self.valid_bookfiles = [
            BookFile.from_args(
                self.book_title_sort,
                file_dict["name"],
                self.metadata_dir,
                self.dir_vars,
                ".",
                file_dict["hash"],
            )
            for file_dict in self.file_dicts
        ]

    def test_multiple(self) -> None:
        """Test unsorted sequence input."""
        self.assertSequenceEqual(
            self.valid_bookfiles,
            _get_files(
                list(reversed(self.file_dicts)),
                self.book_title_sort,
                self.metadata_dir,
                self.dir_vars,
            ),
        )

    def test_single(self) -> None:
        """Test dict input."""
        self.assertSequenceEqual(
            self.valid_bookfiles[:1],
            _get_files(
                self.file_dicts[0],
                self.book_title_sort,
                self.metadata_dir,
                self.dir_vars,
            ),
        )

    def test_error_duplicate(self) -> None:
        """Error with duplicate sequence input."""
        dup = self.file_dicts[0]["name"]
        self.file_dicts[1]["name"] = dup
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            _get_files(
                self.file_dicts, self.book_title_sort, self.metadata_dir, self.dir_vars
            )
        self.assertEqual(
            (
                f"ERROR: duplicate file with name '{dup}' found in "
                f"'{get_metadata_fn(self.metadata_dir)}'."
            ),
            str(cm.exception),
        )


class TestGetKeyValues(SimpleEbookManagerTestCase):
    """Test _get_keyvalues."""

    def setUp(self) -> None:
        self.kvs_input: dict[str, Optional[str]] = {"a": "1", "b": "2"}
        self.output = [
            BookKeyValue(k, v) for k, v in self.kvs_input.items() if v is not None
        ]
        self.fieldname = "x"
        self.metadata_dir = Path("y")
        super().setUp()

    def test_none(self) -> None:
        """Test None input."""
        self.assertSequenceEqual(
            [], _get_keyvalues(None, self.fieldname, self.metadata_dir)
        )

    def test_unsorted(self) -> None:
        """Test unsorted input."""
        self.assertSequenceEqual(
            self.output,
            _get_keyvalues(
                dict(reversed(self.kvs_input.items())),
                self.fieldname,
                self.metadata_dir,
            ),
        )

    def test_error_none_value(self) -> None:
        """Error if a keyvalue value is None."""
        self.kvs_input["c"] = None
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            _get_keyvalues(self.kvs_input, self.fieldname, self.metadata_dir)
        self.assertEqual(
            (
                f"ERROR: key 'c' in keyvalue field '{self.fieldname}' in "
                f"'{get_metadata_fn(self.metadata_dir)}' has a null value."
            ),
            str(cm.exception),
        )


class TestSortDisplay(SimpleEbookManagerTestCase):
    """Test SortDisplay."""

    def setUp(self) -> None:
        self.low = "a"
        self.high = "b"
        super().setUp()

    def test_key(self) -> None:
        """Test with key."""
        key = "c"
        sd = SortDisplay(self.low, self.high, key)
        self.assertEqual(key, sd.key)

    def test_error_no_key(self) -> None:
        """Test without key."""
        sd = SortDisplay(self.low, self.high)
        with self.assertRaises(SimpleEbookManagerException) as cm:
            print(sd.key)
        self.assertEqual(f"key for 'sort={self.low}' is None", str(cm.exception))

    def test_sort(self) -> None:
        """Test sorting."""
        self.assertTrue(
            SortDisplay(self.low, self.low) < SortDisplay(self.high, self.low)
        )


class TestGetSortDisplays(SimpleEbookManagerTestCase):
    """Test _get_sortdisplays."""

    def setUp(self) -> None:
        self.input_str = "a"
        self.input_dict = {"sort": "b", "display": "c"}
        self.assertTrue(self.input_str < self.input_dict["sort"])
        self.d_type = "x"
        self.metadata_dir = Path("y")
        super().setUp()

    def test_none(self) -> None:
        """Test None input."""
        self.assertSequenceEqual(
            [], _get_sortdisplays(None, self.d_type, self.metadata_dir)
        )

    def test_str(self) -> None:
        """Test str input."""
        self.assertSequenceEqual(
            [SortDisplay(self.input_str, self.input_str)],
            _get_sortdisplays(self.input_str, self.d_type, self.metadata_dir),
        )

    def test_dict(self) -> None:
        """Test dict input."""
        self.assertSequenceEqual(
            [SortDisplay(self.input_dict["sort"], self.input_dict["display"])],
            _get_sortdisplays(self.input_dict, self.d_type, self.metadata_dir),
        )

    def test_unsorted(self) -> None:
        """Test unsorted sequence input."""
        self.assertSequenceEqual(
            [
                SortDisplay(self.input_str, self.input_str),
                SortDisplay(self.input_dict["sort"], self.input_dict["display"]),
            ],
            _get_sortdisplays(
                [self.input_dict, self.input_str], self.d_type, self.metadata_dir
            ),
        )

    def test_error_duplicates(self) -> None:
        """Error with duplicate SortDisplays."""
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            _get_sortdisplays(
                [{"display": "a", "sort": "b"}, {"display": "a", "sort": "c"}],
                self.d_type,
                self.metadata_dir,
            )
        self.assertEqual(
            (
                f"ERROR: duplicate '{self.d_type}' data 'display=a' found in "
                f"'{get_metadata_fn(self.metadata_dir)}'."
            ),
            str(cm.exception),
        )

        with self.assertRaises(SimpleEbookManagerExit) as cm:
            _get_sortdisplays(
                [{"display": "b", "sort": "a"}, {"display": "c", "sort": "a"}],
                self.d_type,
                self.metadata_dir,
            )
        self.assertEqual(
            (
                f"ERROR: duplicate '{self.d_type}' data 'sort=a' found in "
                f"'{get_metadata_fn(self.metadata_dir)}'."
            ),
            str(cm.exception),
        )


class TestGetString(SimpleEbookManagerTestCase):
    """Test _get_string."""

    def setUp(self) -> None:
        self.name = "x"
        self.schema_item = SchemaItemTypes.String(self.name, inline=True)
        self.title_prefix = "z"
        super().setUp()

    def test_inline_non_none(self) -> None:
        """Test inline with non-None value."""
        self.assertEqual(
            "a",
            _get_string(
                {self.name: "a"},
                SchemaItemTypes.String(self.name, inline=True),
                Path("."),
                self.title_prefix,
            ),
        )

    def test_inline_none(self) -> None:
        """Test inline with None value."""
        self.assertIsNone(
            _get_string(
                {self.name: None},
                SchemaItemTypes.String(self.name, inline=True),
                Path("."),
                self.title_prefix,
            ),
        )

    def test_non_inline_non_none(self) -> None:
        """Test non-inline with non-None value."""
        metadata_dir = self.get_t_dir()
        text = "asdf\n"
        write_text(get_string_fn(metadata_dir, self.name), f"{self.title_prefix}{text}")
        self.assertEqual(
            text,
            _get_string(
                {},
                SchemaItemTypes.String(self.name, inline=False),
                metadata_dir,
                self.title_prefix,
            ),
        )

    def test_non_inline_none(self) -> None:
        """Test non-inline with None value."""
        metadata_dir = self.get_t_dir()
        self.assertIsNone(
            _get_string(
                {},
                SchemaItemTypes.String(self.name, inline=False),
                metadata_dir,
                self.title_prefix,
            )
        )

    def test_error_non_inline_defined_in_metadata(self) -> None:
        """Error if non-inline value defined in metadata."""
        metadata_dir = self.get_t_dir()
        text = "asdf\n"
        write_text(get_string_fn(metadata_dir, self.name), f"{self.title_prefix}{text}")
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            _get_string(
                {self.name: "a"},
                SchemaItemTypes.String(self.name, inline=False),
                metadata_dir,
                self.title_prefix,
            )
        self.assertEqual(
            (
                f"ERROR: '{self.name}' data found in '{get_metadata_fn(metadata_dir)}' but field "
                "is inline: false in the schema."
            ),
            str(cm.exception),
        )


class TestBook(SimpleEbookManagerTestCase):
    """Test Book."""

    def setUp(self) -> None:
        self.dir_vars = (DirVar("name1", "."), DirVar("name2", "."))
        self.schema = read_schema(fn=VALID_SCHEMA_FN)
        for item in self.schema:
            if isinstance(item, SchemaItemTypes.Date) and item.name == "date_published":
                self.dt_fmt = item.input_format
                break
        self.desc_fieldname = "description"
        super().setUp()

    def _test_from_args(self, b_dir: Path) -> None:
        """General method to test creating Book from b_dir."""
        metadata = read_metadata(b_dir)
        book = Book.from_args(b_dir, self.dir_vars, self.schema)

        match metadata["book_title"]:
            case str(sort):
                self.assertEqual(SortDisplay(sort, sort), book.title)
            case {"sort": sort, "display": display}:
                self.assertEqual(SortDisplay(sort, display), book.title)

        self.assertEqual(f"# Title: {book.title.display}\n#\n", book.str_title_prefix)
        self.assertEqual(b_dir, book.metadata_dir)
        self.assertSequenceEqual(
            _get_files(
                metadata["book_files"],
                book.title.sort,
                book.metadata_dir,
                self.dir_vars,
            ),
            book.files,
        )

        desc_fn = get_string_fn(b_dir, self.desc_fieldname)
        valid_bookfields = _BookFields(
            dates={
                "date_published": _get_date(metadata["date_published"], self.dt_fmt)
            },
            keyvalues={"ids": _get_keyvalues(metadata["ids"], "ids", b_dir)},
            sortdisplays={
                "authors": _get_sortdisplays(metadata["authors"], "authors", b_dir)
            },
            strings={
                "subtitle": metadata["subtitle"],
                self.desc_fieldname: read_text(desc_fn).removeprefix(
                    book.str_title_prefix
                )
                if desc_fn.is_file()
                else None,
            },
        )
        self.assertEqual(valid_bookfields, book.fields)

    def test_creating_complete(self) -> None:
        """Test creating Book COMPLETE."""
        self._test_from_args(ValidBookDirs.COMPLETE)

    def test_creating_compressed_fields(self) -> None:
        """Test creating Book COMPRESSED_FIELDS."""
        self._test_from_args(ValidBookDirs.COMPRESSED_FIELDS)

    def test_creating_minimal(self) -> None:
        """Test creating Book MINIMAL."""
        self._test_from_args(ValidBookDirs.MINIMAL)

    def test_creating_overlap(self) -> None:
        """Test creating Book OVERLAP."""
        self._test_from_args(ValidBookDirs.OVERLAP)

    def _assert_write_metadata_valid(
        self,
        b_dir: Path,
        *,
        valid_dir: Optional[Path] = None,
        newline: Newline = Newline.POSIX,
        replace_unicode: bool = False,
        schema: Optional[Schema] = None,
    ) -> None:
        """General method to test Book.write_metadata."""
        valid_dir = valid_dir if valid_dir is not None else b_dir
        schema = schema if schema is not None else self.schema

        book = Book.from_args(b_dir, self.dir_vars, schema)
        t_dir = self.get_t_dir()
        test_fns = book.write_metadata(
            t_dir, schema, newline=newline, replace_unicode=replace_unicode
        )
        valid_fns = [get_metadata_fn(t_dir)]
        for item in schema:
            if isinstance(item, SchemaItemTypes.String) and not item.inline:
                item_fn = get_string_fn(t_dir, item.name)
                if (valid_dir / item_fn.name).is_file():
                    valid_fns.append(item_fn)

        self.assertSequenceEqual(valid_fns, test_fns)
        for fn in valid_fns:
            self.assertTrue(cmp(valid_dir / fn.name, fn))

    def test_writing_complete(self) -> None:
        """Test writing Book COMPLETE."""
        self._assert_write_metadata_valid(ValidBookDirs.COMPLETE)

    def test_writing_compressed_fields(self) -> None:
        """Test writing Book COMPRESSED_FIELDS."""
        self._assert_write_metadata_valid(ValidBookDirs.COMPRESSED_FIELDS)

    def test_writing_minimal(self) -> None:
        """Test writing Book MINIMAL."""
        self._assert_write_metadata_valid(ValidBookDirs.MINIMAL)

    def test_writing_overlap(self) -> None:
        """Test writing Book OVERLAP."""
        self._assert_write_metadata_valid(ValidBookDirs.OVERLAP)

    def test_writing_arg_newline(self) -> None:
        """Test write_metadata newline arg."""
        posix_b_dir = ValidBookDirs.COMPLETE
        windows_b_dir = self.get_t_dir() / "windows"
        shutil.copytree(posix_b_dir, windows_b_dir)

        # Prepare windows dir
        windows_metadata_fn = get_metadata_fn(windows_b_dir)
        write_text(
            windows_metadata_fn, read_text(windows_metadata_fn), newline=Newline.WINDOWS
        )
        windows_desc_fn = get_string_fn(windows_b_dir, self.desc_fieldname)
        write_text(windows_desc_fn, read_text(windows_desc_fn), newline=Newline.WINDOWS)

        self._assert_write_metadata_valid(
            posix_b_dir, valid_dir=windows_b_dir, newline=Newline.WINDOWS
        )
        self._assert_write_metadata_valid(
            windows_b_dir, valid_dir=posix_b_dir, newline=Newline.POSIX
        )

    def test_writing_arg_replace_unicode(self) -> None:
        """Test write_metadata replace_unicode arg."""
        orig_b_dir = ValidBookDirs.COMPLETE
        orig_desc = read_text(get_string_fn(orig_b_dir, self.desc_fieldname))

        # prepare Unicode dir
        t_dir = self.get_t_dir()
        unicode_b_dir = t_dir / "unicode"
        shutil.copytree(orig_b_dir, unicode_b_dir)
        write_text(
            get_string_fn(unicode_b_dir, self.desc_fieldname),
            orig_desc + UNICODE_LINE,
        )

        # test no change with replace_unicode=False
        self._assert_write_metadata_valid(unicode_b_dir, replace_unicode=False)

        # prepare ASCII dir
        ascii_b_dir = t_dir / "ascii"
        shutil.copytree(orig_b_dir, ascii_b_dir)
        write_text(
            get_string_fn(ascii_b_dir, self.desc_fieldname), orig_desc + ASCII_LINE
        )

        # test Unicode output matches ASCII dir with replace_unicode=True
        self._assert_write_metadata_valid(
            unicode_b_dir, valid_dir=ascii_b_dir, replace_unicode=True
        )

    def test_writing_comprehensive(self) -> None:
        """Comprehensive test that all fields are written correctly."""
        schema = Schema(
            (
                SchemaItemTypes.Title("book_title"),
                SchemaItemTypes.Date("date_none", "%Y-%b-%d", "%Y-%m-%d"),
                SchemaItemTypes.Date("date_not_none", "%Y-%b-%d", "%Y-%m-%d"),
                SchemaItemTypes.File("files"),
                SchemaItemTypes.KeyValue("kv_none", "kl1", "vl1"),
                SchemaItemTypes.KeyValue("kv_not_none", "kl2", "vl2"),
                SchemaItemTypes.SortDisplay("sd_none"),
                SchemaItemTypes.SortDisplay("sd_single_same"),
                SchemaItemTypes.SortDisplay("sd_single_different"),
                SchemaItemTypes.SortDisplay("sd_multiple"),
                SchemaItemTypes.String("str_none", True),
                SchemaItemTypes.String("str_not_none", True),
            )
        )

        b_dir = self.get_t_dir()
        metadata_fn = get_metadata_fn(b_dir)
        metadata = {
            "date_none": None,
            "date_not_none": "2000-Jan-31",
            "files": {"directory": "a", "hash": "b", "name": "c"},
            "kv_none": None,
            "kv_not_none": {"a": "b"},
            "book_title": "a",
            "sd_none": None,
            "sd_single_same": "a",
            "sd_single_different": {"display": "a", "sort": "b"},
            "sd_multiple": ["a", {"display": "b", "sort": "c"}],
            "str_none": None,
            "str_not_none": "a",
        }
        write_json(metadata_fn, metadata)
        self._assert_write_metadata_valid(b_dir, schema=schema)

        # expand title and files fields
        metadata["book_title"] = {"display": "a", "sort": "b"}
        metadata["files"] = [
            {"directory": "a", "hash": "b", "name": "c"},
            {"directory": "a", "hash": "b", "name": "d"},
        ]
        write_json(metadata_fn, metadata)
        self._assert_write_metadata_valid(b_dir, schema=schema)


class TestTextFunctions(SimpleEbookManagerTestCase):
    """Test text cleanup functions."""

    def test_remove_whitespace(self) -> None:
        """Test _remove_whitespace."""
        valid_text = "a\n" * 2
        w_s = " \t"
        start_text = f"{w_s}a{w_s}\n" * 2
        self.assertEqual(valid_text, _remove_whitespace(start_text))
        self.assertEqual(valid_text, _remove_whitespace(valid_text))

    def test_replace_unicode(self) -> None:
        """Test _replace_unicode."""
        self.assertEqual(ASCII_LINE, _replace_unicode(UNICODE_LINE))
        self.assertEqual(ASCII_LINE, _replace_unicode(ASCII_LINE))
