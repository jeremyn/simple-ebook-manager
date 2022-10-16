"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Test src.db.

Optionally set the DB_DUMP_DIR environment variable to $DIR for TestDb.test_int to dump a modified
test_conn to $DIR/books.sql.

"""
import os
import shutil
from pathlib import Path
from sqlite3 import Connection, Row, connect
from typing import Any, Optional
from unittest.mock import patch

from src.command import Args, Command
from src.db import get_cmd
from src.util import (
    LOG_LEVEL,
    SchemaItemTypes,
    get_db_fn,
    get_log_records,
    get_schema_fn,
    read_text,
)
from tests.base import (
    EXAMPLE_LIBRARY_DIR,
    PLACEHOLDER_DIR_STR,
    USER_SQL_FN,
    VALID_DB_SQL_FN,
)
from tests.test_command import CommandTestCase


def _dump_db(conn: Connection, dump_fn: Path, temp_dir_str: str) -> None:
    """Dump conn to dump_fn and replace temp_dir_str with PLACEHOLDER_DIR_STR.

    Use this to update the valid dump reference.

    """
    rows = conn.execute(
        "SELECT name FROM sqlite_schema WHERE type='view' ORDER BY name"
    ).fetchall()
    new_tables = []
    for row in rows:
        new_tables.append(f"mat_{row['name']}")
        conn.execute(f"CREATE TABLE {new_tables[-1]} AS SELECT * FROM {row['name']}")

    # pylint: disable=import-outside-toplevel
    from pathlib import PurePosixPath

    from src.util import write_text

    # pylint: enable=import-outside-toplevel

    joiner = str(PurePosixPath(Path(PLACEHOLDER_DIR_STR) / "x"))[:-1]
    splitter = str(Path(temp_dir_str) / "x")[:-1]
    write_text(
        dump_fn,
        "\n".join([joiner.join(line.split(splitter)) for line in conn.iterdump()]),
    )

    for table in new_tables:
        conn.execute(f"DROP TABLE {table}")


def _get_relative_to(old_path_str: str, new_path_str: str) -> str:
    """Replace old_path_str with new_path_str."""
    return str(new_path_str / Path(old_path_str).relative_to(PLACEHOLDER_DIR_STR))


class TestDb(CommandTestCase):
    """Test the command."""

    CMD: Command

    @classmethod
    def setUpClass(cls) -> None:
        cls.CMD = get_cmd()
        super().setUpClass()

    def _assert_view_data_correct(self, conn: Connection) -> None:
        """Assert that views in conn match materialized views, then drop materialized views."""
        rows = conn.execute(
            "SELECT name FROM sqlite_schema WHERE type='view' ORDER BY name"
        ).fetchall()
        for row in rows:
            mat_table = f"mat_{row['name']}"
            self.assertSequenceEqual(
                conn.execute(f"SELECT * FROM {mat_table}").fetchall(),
                conn.execute(f"SELECT * FROM {row['name']}").fetchall(),
            )
            conn.execute(f"DROP TABLE {mat_table}")

    def _get_sql_data(self, conn: Connection) -> dict[str, Any]:
        """Get sql data from conn."""
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_schema WHERE type IN ('table', 'view') ORDER BY name"
        ).fetchall()
        sql_data = {
            row["name"]: {
                "sql": row["sql"],
                "data": conn.execute(f"SELECT * FROM {row['name']}").fetchall(),
            }
            for row in rows
        }
        self.assertTrue(sql_data)
        return sql_data

    def _standardize_conn(self, conn: Connection, new_path_str: str) -> None:
        """Standardize data in conn."""
        for item in self.schema:
            if isinstance(item, SchemaItemTypes.File):
                rows = conn.execute(
                    f"""
                    SELECT file_full_path, metadata_directory, book_pkey, file_name
                    FROM book_{item.name}
                    """
                ).fetchall()
                for row in rows:
                    conn.execute(
                        f"""
                        UPDATE book_{item.name}
                        SET file_full_path=:file_full_path, metadata_directory=:metadata_directory
                        WHERE book_pkey=:book_pkey AND file_name=:file_name
                        """,
                        {
                            "file_full_path": _get_relative_to(
                                row["file_full_path"], new_path_str
                            ),
                            "metadata_directory": _get_relative_to(
                                row["metadata_directory"], new_path_str
                            ),
                            "book_pkey": row["book_pkey"],
                            "file_name": row["file_name"],
                        },
                    )
        rows = conn.execute("SELECT pkey, metadata_directory FROM book").fetchall()
        for row in rows:
            conn.execute(
                "UPDATE book SET metadata_directory=:metadata_directory WHERE pkey=:pkey",
                {
                    "metadata_directory": _get_relative_to(
                        row["metadata_directory"], new_path_str
                    ),
                    "pkey": row["pkey"],
                },
            )

    @patch("src.db.db._BATCH_SIZE", 3)
    def _test_main(
        self, *, use_uuid_key: bool, db_dump_dir_str: Optional[str] = None
    ) -> None:
        """General method for testing db command."""
        db_fn = get_db_fn(self.l_dirs[0])
        db_fn.touch()

        main_args = (
            [
                Args.DIR_VARS.opt,
                "name1",
                ".",
                Args.DIR_VARS.opt,
                "name2",
                ".",
            ]
            + [Args.LIBRARY_DIRS.opt]
            + [str(l_dir) for l_dir in self.l_dirs]
            + [Args.USER_SQL_FILE.opt, str(USER_SQL_FN)]
        )
        if use_uuid_key:
            main_args.append(Args.USE_UUID_KEY.opt)

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(main_args)

        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(self.l_dirs[0])}'.",
                f"Collecting book data and assigning {'UUID' if use_uuid_key else 'integer'} keys.",
                f"Overwriting existing database file '{db_fn}'.",
                f"Creating '{db_fn}'.",
                "Inserted data type 'authors'.",
                "Inserted 3 books into database.",
                "Inserted 4 books into database.",
                f"Running user SQL file '{USER_SQL_FN}'.",
                f"Finished creating '{db_fn}'.",
            ],
            get_log_records(cm),
        )

        test_conn = connect(db_fn)
        test_conn.row_factory = Row
        if db_dump_dir_str is not None:
            _dump_db(
                test_conn,
                Path(db_dump_dir_str) / VALID_DB_SQL_FN.name,
                str(self.l_dirs[0]),
            )
        test_data = self._get_sql_data(test_conn)

        valid_conn = connect(":memory:")
        valid_conn.row_factory = Row
        valid_conn.executescript(read_text(VALID_DB_SQL_FN))
        self._assert_view_data_correct(valid_conn)
        with valid_conn:
            self._standardize_conn(valid_conn, str(self.l_dirs[0]))
        valid_data = self._get_sql_data(valid_conn)

        self.assertEqual(valid_data.keys(), test_data.keys())
        for v_data, t_data in zip(valid_data.values(), test_data.values()):
            if use_uuid_key:
                self.assertEqual(len(v_data["data"]), len(t_data["data"]))
            else:
                self.assertEqual(v_data["sql"], t_data["sql"])
                self.assertEqual(v_data["data"], t_data["data"])

    def test_int(self) -> None:
        """Test db command with integer keys."""
        self._test_main(use_uuid_key=False, db_dump_dir_str=os.getenv("DB_DUMP_DIR"))

    def test_uuid(self) -> None:
        """Test db command with UUID keys."""
        self._test_main(use_uuid_key=True)

    def test_quickstart(self) -> None:
        """Test the quickstart example."""
        l_dir = self.t_dir / "example_library_dir"
        shutil.copytree(EXAMPLE_LIBRARY_DIR, l_dir)

        with self.assertLogs(level=LOG_LEVEL) as cm:
            self._run_cmd_main(
                [Args.LIBRARY_DIRS.opt, str(l_dir)]
                + [Args.OUTPUT_DIR.opt, str(self.t_dir)]
            )
        db_fn = get_db_fn(self.t_dir)
        self.assertSequenceEqual(
            [
                f"Using schema from '{get_schema_fn(l_dir)}'.",
                "Collecting book data and assigning integer keys.",
                f"Creating '{db_fn}'.",
                "Inserted data type 'authors'.",
                "Inserted 2 books into database.",
                f"Finished creating '{db_fn}'.",
            ],
            get_log_records(cm),
        )
        test_conn = connect(db_fn)
        self.assertEqual(
            2, test_conn.execute("SELECT count(*) FROM v_summary;").fetchone()[0]
        )

    def test_combos(self) -> None:
        """Test that the command runs without error, don't check output."""
        self._run_arg_combos(
            [
                [[Args.DIR_VARS.opt, "name1", ".", Args.DIR_VARS.opt, "name2", "."]],
                [[Args.LIBRARY_DIRS.opt] + [str(l_dir) for l_dir in self.l_dirs]],
                [[Args.OUTPUT_DIR.opt, str(self.l_dirs[0])], []],
                [[Args.SCHEMA.opt, str(get_schema_fn(self.l_dirs[0]))], []],
                [[Args.USE_UUID_KEY.opt], []],
                [[Args.USER_SQL_FILE.opt, str(USER_SQL_FN)], []],
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
