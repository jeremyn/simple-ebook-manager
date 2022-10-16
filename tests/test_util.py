"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.util.

"""
import json
import shutil
from pathlib import Path

from src.util import (
    LOG_LEVEL,
    Algorithm,
    Newline,
    Schema,
    SchemaItemTypes,
    SimpleEbookManagerException,
    SimpleEbookManagerExit,
    cmp,
    get_csv_fn,
    get_db_fn,
    get_file_hashes,
    get_log_records,
    get_metadata_fn,
    get_newline,
    get_schema_fn,
    get_string_fn,
    read_json,
    read_metadata,
    read_schema,
    read_text,
    write_csv,
    write_json,
    write_schema,
    write_text,
)
from src.util.schema import _SchemaItemBase
from tests.base import (
    UTF_8,
    VALID_LIBRARY_DIR,
    VALID_SCHEMA_FN,
    SimpleEbookManagerTestCase,
    ValidBookDirs,
)


class TestGetFilename(SimpleEbookManagerTestCase):
    """Test "get fn" functions."""

    def setUp(self) -> None:
        self.dir_ = Path("my_dir")
        super().setUp()

    def test_get_csv_fn(self) -> None:
        """Test get_csv_fn."""
        self.assertEqual(self.dir_ / "books.csv", get_csv_fn(self.dir_))
        self.assertEqual(self.dir_ / "a.csv", get_csv_fn(self.dir_, "a"))
        self.assertEqual(Path("a.csv"), get_csv_fn(None, "a"))

    def test_get_db_fn(self) -> None:
        """Test get_db_fn."""
        self.assertEqual(self.dir_ / "books.sqlite3", get_db_fn(self.dir_))

    def test_get_metadata_fn(self) -> None:
        """Test get_metadata_fn."""
        self.assertEqual(self.dir_ / "metadata.json", get_metadata_fn(self.dir_))

    def test_get_schema_fn(self) -> None:
        """Test get_schema_fn."""
        self.assertEqual(self.dir_ / "schema.json", get_schema_fn(self.dir_))

    def test_get_string_fn(self) -> None:
        """Test get_string_fn."""
        self.assertEqual(self.dir_ / "a.txt", get_string_fn(self.dir_, "a"))


class TestGetNewline(SimpleEbookManagerTestCase):
    """Test get_newline."""

    def test_both(self) -> None:
        """Test with both args, prefer newline arg."""
        self.assertEqual(Newline.WINDOWS, get_newline("windows", VALID_SCHEMA_FN))

    def test_fn_only(self) -> None:
        """Test with only fn arg."""
        self.assertEqual(Newline.POSIX, get_newline(None, VALID_SCHEMA_FN))

    def test_error(self) -> None:
        """Error if no newline and fn arg has problems."""
        temp_fn = self.get_t_dir() / "a.txt"
        write_text(temp_fn, "a\nb\r\n")
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            get_newline(None, temp_fn)

        self.assertEqual(
            f"ERROR: newline not specified and autodetect failed on '{temp_fn}'.",
            str(cm.exception),
        )


class TestSchema(SimpleEbookManagerTestCase):
    """Test schema functions, mostly read_schema."""

    schema: Schema
    schema_items: tuple[_SchemaItemBase, ...]
    title_fieldname: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.title_fieldname = "book_title"
        cls.schema_items = (
            SchemaItemTypes.Title(cls.title_fieldname),
            SchemaItemTypes.String("subtitle", inline=True),
            SchemaItemTypes.SortDisplay("authors"),
            SchemaItemTypes.File("book_files"),
            SchemaItemTypes.KeyValue(
                "ids", key_label="id_type", value_label="id_value"
            ),
            SchemaItemTypes.Date(
                "date_published", input_format="%Y-%b-%d", output_format="%Y-%m-%d"
            ),
            SchemaItemTypes.String("description", inline=False),
        )
        cls.schema = Schema(cls.schema_items)
        super().setUpClass()

    def test_schema(self) -> None:
        """Test Schema methods."""
        self.assertSequenceEqual(self.schema_items, list(self.schema))
        self.assertEqual(self.title_fieldname, self.schema.title_fieldname)

    def test_read_fn_only(self) -> None:
        """Test with fn only."""
        with self.assertLogs(level=LOG_LEVEL) as cm:
            self.assertEqual(self.schema, read_schema(fn=VALID_SCHEMA_FN))
        self.assertSequenceEqual(
            [f"Using schema from '{VALID_SCHEMA_FN}'."], get_log_records(cm)
        )

    def test_read_fn_error_duplicate_name(self) -> None:
        """Error if there are duplicate item names."""
        schema_fn = get_schema_fn(self.get_t_dir())
        write_text(
            schema_fn,
            '{"a": "sortdisplay", "a": "sortdisplay", "1": "file", "2": "title"}',
        )

        with self.assertRaises(SimpleEbookManagerExit) as cm:
            read_schema(fn=schema_fn)

        self.assertEqual(
            f"ERROR: duplicate key 'a' found in '{schema_fn}'.", str(cm.exception)
        )

    def test_read_fn_error_reserved_name(self) -> None:
        """Error if a reserved name is found."""
        schema_fn = get_schema_fn(self.get_t_dir())
        for name in (names_reserved := ["books"]):
            write_schema(schema_fn, {name: "file", "b": "title"})

            with self.assertRaises(SimpleEbookManagerExit) as cm:
                read_schema(fn=schema_fn)

            self.assertEqual(
                (
                    f"ERROR: reserved name '{name}' found in '{schema_fn}' (reserved name(s) "
                    f"are: {', '.join(names_reserved)})."
                ),
                str(cm.exception),
            )

    def test_read_fn_error_required_type(self) -> None:
        """Error if a required type is missing.."""
        schema_fn = get_schema_fn(self.get_t_dir())
        for type_ in (types_required := ["file", "title"]):
            write_schema(
                schema_fn,
                {str(i): t for i, t in enumerate(types_required) if t != type_},
            )

            with self.assertRaises(SimpleEbookManagerExit) as cm:
                read_schema(fn=schema_fn)

            self.assertEqual(
                f"ERROR: item with required type '{type_}' not found in '{schema_fn}'.",
                str(cm.exception),
            )

    def test_read_fn_error_problem_processing_type(self) -> None:
        """Error if there is a problem processing the type."""
        schema_fn = get_schema_fn(self.get_t_dir())
        write_schema(schema_fn, {"a": "asdf", "1": "file", "2": "title"})

        with self.assertRaises(SimpleEbookManagerExit) as cm:
            read_schema(fn=schema_fn)

        self.assertEqual(
            f"ERROR: problem processing type for item name 'a' found in '{schema_fn}'.",
            str(cm.exception),
        )

    def test_read_fn_error_invalid_duplicate_type(self) -> None:
        """Error if there are invalid duplicate types."""
        schema_fn = get_schema_fn(self.get_t_dir())
        types_no_duplicates = ["file", "title"]
        schema_dict = {"1": "file", "2": "title"}
        for type_ in types_no_duplicates:
            schema_dict["a"] = type_
            write_schema(schema_fn, schema_dict)

            with self.assertRaises(SimpleEbookManagerExit) as cm:
                read_schema(fn=schema_fn)

            self.assertEqual(
                (
                    f"ERROR: duplicate items with type '{type_}' found in '{schema_fn}', item "
                    f"names: {', '.join([k for k, v in schema_dict.items() if v == type_])}."
                ),
                str(cm.exception),
            )

    def test_read_fn_and_dirs(self) -> None:
        """Specify both args, should prefer fn."""
        l_dir = self.get_t_dir()
        write_schema(get_schema_fn(l_dir), {"1": "file", "2": "title"})
        with self.assertLogs(level=LOG_LEVEL) as cm:
            self.assertEqual(self.schema, read_schema(fn=VALID_SCHEMA_FN, dirs=[l_dir]))
        self.assertSequenceEqual(
            [f"Using schema from '{VALID_SCHEMA_FN}'."], get_log_records(cm)
        )

    def test_read_dirs(self) -> None:
        """Only specify dirs arg."""
        with self.assertLogs(level=LOG_LEVEL) as cm:
            self.assertEqual(self.schema, read_schema(dirs=[VALID_LIBRARY_DIR]))
        self.assertSequenceEqual(
            [f"Using schema from '{get_schema_fn(VALID_LIBRARY_DIR)}'."],
            get_log_records(cm),
        )

    def test_read_dirs_error_no_schema(self) -> None:
        """Error when no schema found in any dir."""
        l_dirs = [self.get_t_dir(), self.get_t_dir()]
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            read_schema(dirs=l_dirs)
        self.assertEqual(
            (
                f"ERROR: schema filename not provided and no '{str(get_schema_fn(None))}' found in "
                "dirs."
            ),
            str(cm.exception),
        )

    def test_read_dirs_only_second_dir_has_schema(self) -> None:
        """Don't error if the first dir doesn't have a schema but the second does."""
        l_dirs = [self.get_t_dir(), self.get_t_dir()]
        shutil.copy(VALID_SCHEMA_FN, get_schema_fn(l_dirs[1]))
        with self.assertLogs(level=LOG_LEVEL) as cm:
            self.assertEqual(self.schema, read_schema(dirs=l_dirs))
        self.assertSequenceEqual(
            [f"Using schema from '{get_schema_fn(l_dirs[1])}'."], get_log_records(cm)
        )

    def test_read_dirs_matching_schemas(self) -> None:
        """Accept two dirs when their schemas match."""
        schema_fns = [VALID_SCHEMA_FN, get_schema_fn(self.get_t_dir())]
        shutil.copy(*schema_fns)

        with self.assertLogs(level=LOG_LEVEL) as cm:
            test_schema = read_schema(dirs=[fn.parent for fn in schema_fns])
        self.assertEqual(self.schema, test_schema)
        msg = "', '".join([str(fn) for fn in schema_fns])
        self.assertSequenceEqual(
            [f"Using matching schemas from: '{msg}'."], get_log_records(cm)
        )

    def test_read_dirs_error_conflicting_schemas(self) -> None:
        """Error if two dirs have conflicting schemas."""
        temp_schema_fn = get_schema_fn(self.get_t_dir())
        write_schema(temp_schema_fn, {"a": "file", "b": "title"})

        schema_fns = [VALID_SCHEMA_FN, temp_schema_fn]
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            read_schema(dirs=[fn.parent for fn in schema_fns])
        self.assertEqual(
            "ERROR: schema filename not provided and at least two dir schemas conflict.",
            str(cm.exception),
        )

    def test_read_error_no_input(self) -> None:
        """Error when no input arg set."""
        with self.assertRaises(SimpleEbookManagerException) as cm:
            read_schema()
        self.assertEqual("at least one input arg must be set", str(cm.exception))


class TestGetFileHashes(SimpleEbookManagerTestCase):
    """Test get_file_hashes."""

    def test_get_file_hashes(self) -> None:
        """Test get_file_hashes."""
        b_dir = ValidBookDirs.COMPLETE
        file_dicts = read_metadata(b_dir)["book_files"]
        fns = [b_dir / f_dict["name"] for f_dict in file_dicts]
        self.assertEqual(
            {
                fns[
                    0
                ]: "sha256:24bb72ce1c4afcb071d1c9193f7efde30cc6b02d1f83f7a40db001eb123dff7f",
                fns[
                    1
                ]: "sha256:e28eafdf452c98350c08295bedc10536e811f4e24328f6ea3d59a5c4a5960e58",
            },
            get_file_hashes(fns, Algorithm.SHA256),
        )
        self.assertEqual(
            {fns[0]: file_dicts[0]["hash"], fns[1]: file_dicts[1]["hash"]},
            get_file_hashes(fns, Algorithm.MD5),
        )


class TestReadFunctions(SimpleEbookManagerTestCase):
    """Test read functions."""

    def test_read_json(self) -> None:
        """Test read_json."""
        valid_json_text = '{"a": 1}'
        temp_fn = self.get_t_dir() / "test_output.json"
        temp_fn.write_text(valid_json_text, encoding=UTF_8)
        self.assertEqual(json.loads(valid_json_text), read_json(temp_fn))

    def test_read_json_error_duplicate_key(self) -> None:
        """Error read_json if duplicate keys found."""
        temp_fn = self.get_t_dir() / "test_output.json"
        error_msg = f"ERROR: duplicate key 'a' found in '{temp_fn}'."

        # error with top level duplicates
        temp_fn.write_text('{"a": 1, "a": 2}', encoding=UTF_8)
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            read_json(temp_fn)
        self.assertEqual(error_msg, str(cm.exception))

        # error with nested duplicates
        temp_fn.write_text('{"b": 1, "c": {"a": 2, "a": 3}}', encoding=UTF_8)
        with self.assertRaises(SimpleEbookManagerExit) as cm:
            read_json(temp_fn)
        self.assertEqual(error_msg, str(cm.exception))

    def test_read_metadata(self) -> None:
        """Test read_metadata."""
        valid_json_text = '{"a": 1}'
        temp_metadata_fn = get_metadata_fn(self.get_t_dir())
        temp_metadata_fn.write_text(valid_json_text, encoding=UTF_8)
        valid_json_data = json.loads(valid_json_text)
        self.assertEqual(valid_json_data, read_metadata(temp_metadata_fn))
        self.assertEqual(valid_json_data, read_metadata(temp_metadata_fn.parent))

    def test_read_text(self) -> None:
        """Test read_text."""
        valid_text = "test text"
        temp_fn = self.get_t_dir() / "test_output.txt"
        with temp_fn.open(mode="w", encoding=UTF_8) as file:
            file.write(valid_text)
        self.assertEqual(valid_text, read_text(temp_fn))


class TestWriteFunctions(SimpleEbookManagerTestCase):
    """Test write functions."""

    def test_write_csv(self) -> None:
        """Test write_csv."""
        col1, col2 = "col1", "col2"
        t_dir = self.get_t_dir()
        test_fn = t_dir / "test_output.csv"
        write_csv(test_fn, [{col1: "a", col2: "b"}, {col1: "c", col2: "d1,d2"}])

        valid_fn = t_dir / "valid_output.csv"
        with valid_fn.open("w", encoding=UTF_8, newline="") as file:
            file.writelines([f"{col1},{col2}\r\n", "a,b\r\n", 'c,"d1,d2"\r\n'])

        self.assertTrue(cmp(valid_fn, test_fn))

    def test_write_json(self) -> None:
        """Test write_json."""
        low, high = "a", "b"
        valid_data = {high: 1, low: 2}
        temp_fn = self.get_t_dir() / "test_output.json"
        # test newlines and sorting
        for newline in Newline:
            write_json(temp_fn, valid_data, newline=newline)
            with temp_fn.open(encoding=UTF_8) as file:
                self.assertSequenceEqual(
                    ["{\n", f'    "{low}": 2,\n', f'    "{high}": 1\n', "}\n"],
                    file.readlines(),
                )
            self.assertEqual(newline.value, file.newlines)

        # test custom_kw
        write_json(temp_fn, valid_data, custom_kw={"sort_keys": False})
        with temp_fn.open(encoding=UTF_8) as file:
            self.assertSequenceEqual(
                ["{\n", f'    "{high}": 1,\n', f'    "{low}": 2\n', "}\n"],
                file.readlines(),
            )

    def test_write_schema(self) -> None:
        """Test write_schema.

        Specifically, test that write_schema doesn't sort dict keys.

        """
        schema_fn = get_schema_fn(self.get_t_dir())
        write_schema(schema_fn, {"b": "type", "a": "type"})
        self.assertSequenceEqual(
            [("b", "type"), ("a", "type")], list(read_json(schema_fn).items())
        )

    def test_write_text(self) -> None:
        """Test write_text."""
        valid_text = "a\nb\n"
        temp_fn = self.get_t_dir() / "test_output.txt"
        # test newlines
        for newline in Newline:
            kwargs = {"newline": newline} if newline == Newline.WINDOWS else {}
            write_text(temp_fn, valid_text, **kwargs)
            with temp_fn.open(encoding=UTF_8) as file:
                self.assertEqual(valid_text, file.read())
            self.assertEqual(newline.value, file.newlines)

        # test that exactly one newline is written at the end
        for i in range(3):
            write_text(temp_fn, "a" + "\n" * i)
            with temp_fn.open(encoding=UTF_8) as file:
                self.assertEqual("a\n", file.read())
