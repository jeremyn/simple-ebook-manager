"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Create a SQLite database file from books.

"""
import logging
from argparse import Namespace
from pathlib import Path
from sqlite3 import Connection, connect
from typing import DefaultDict, Optional

from src.all_metadata import AllMetadata, KeyType
from src.book import Book
from src.command import Args, CmdNames, Command
from src.util import Schema, SchemaItemTypes, get_db_fn, read_schema, read_text

from . import sql

logger = logging.getLogger(__name__)

_BATCH_SIZE = 1000


def _create_tables(conn: Connection, schema: Schema, use_uuid_key: bool) -> None:
    """Create all tables and views for the database."""
    conn.execute(sql.get_create_table_book_sql(schema, use_uuid_key))

    for item in schema:
        match item:
            case SchemaItemTypes.File():
                conn.execute(
                    sql.get_create_table_book_file_sql(item.name, use_uuid_key)
                )
                conn.execute(
                    sql.get_create_view_book_file_sql(item.name, schema.title_fieldname)
                )

            case SchemaItemTypes.KeyValue():
                conn.execute(
                    sql.get_create_table_keyvalue_sql(
                        item.name, item.key_label, item.value_label, use_uuid_key
                    )
                )
                conn.execute(
                    sql.get_create_view_keyvalue_sql(
                        item.name,
                        item.key_label,
                        item.value_label,
                        schema.title_fieldname,
                    )
                )

            case SchemaItemTypes.SortDisplay():
                conn.execute(
                    sql.get_create_table_sortdisplay_sql(item.name, use_uuid_key)
                )
                conn.execute(
                    sql.get_create_table_sortdisplay_join_sql(item.name, use_uuid_key)
                )
                conn.execute(
                    sql.get_create_view_sortdisplay_sql(
                        item.name, schema.title_fieldname
                    )
                )

    conn.execute(sql.get_create_view_summary_sql(schema))


def _insert_sortdisplays(conn: Connection, am: AllMetadata, schema: Schema) -> None:
    """Insert SortDisplays into database."""
    for item in schema:
        if isinstance(item, SchemaItemTypes.SortDisplay):
            conn.executemany(
                sql.get_insert_sortdisplay_sql(item.name),
                [
                    {"pkey": sd.key, "sort": sd.sort, "display": sd.display}
                    for sd in am.fields[item.name]
                ],
            )
            logger.info("Inserted data type '%s'.", item.name)


_InsertValsDict = dict[str, Optional[str]]


def _get_book_insert_vals(
    book: Book, schema: Schema
) -> tuple[_InsertValsDict, dict[str, list[_InsertValsDict]]]:
    """Get insert values for a single book."""
    book_inserts: _InsertValsDict = {
        "pkey": book.title.key,
        "metadata_directory": str(book.metadata_dir),
    }
    post_book_inserts: dict[str, list[_InsertValsDict]] = {}
    for item in schema:
        match item:
            case SchemaItemTypes.Date():
                book_inserts[item.name] = (
                    date_val.as_str(item.output_format)
                    if (date_val := book.fields.dates[item.name]) is not None
                    else None
                )

            case SchemaItemTypes.File():
                sql_ = sql.get_insert_book_file_sql(item.name)
                post_book_inserts[sql_] = []
                for file in book.files:
                    post_book_inserts[sql_].append(
                        {
                            "book_pkey": book.title.key,
                            "file_name": file.basename,
                            "file_hash": file.hash,
                            "file_full_path": str(file.fn),
                            "metadata_directory": str(file.metadata_dir),
                            "file_directory": file.input_dir_str,
                            "dir_vars": ";".join(
                                [str(dir_var) for dir_var in file.dir_vars]
                            ),
                        }
                    )

            case SchemaItemTypes.KeyValue():
                sql_ = sql.get_insert_keyvalue_sql(
                    item.name, item.key_label, item.value_label
                )
                post_book_inserts[sql_] = []
                for k_v in book.fields.keyvalues[item.name]:
                    post_book_inserts[sql_].append(
                        {
                            "book_pkey": book.title.key,
                            item.key_label: k_v.key,
                            item.value_label: k_v.value,
                        }
                    )

            case SchemaItemTypes.SortDisplay():
                sql_ = sql.get_insert_sortdisplay_join_sql(item.name)
                post_book_inserts[sql_] = []
                for val in book.fields.sortdisplays[item.name]:
                    post_book_inserts[sql_].append(
                        {"book_pkey": book.title.key, f"{item.name}_pkey": val.key}
                    )

            case SchemaItemTypes.String():
                book_inserts[item.name] = book.fields.strings[item.name]

            case SchemaItemTypes.Title():
                book_inserts[f"{item.name}_sort"] = book.title.sort
                book_inserts[f"{item.name}_display"] = book.title.display

    return book_inserts, post_book_inserts


def _insert_books_batch(
    conn: Connection, am: AllMetadata, schema: Schema, start: int, end: int
) -> None:
    """Get insert values for a batch of books."""
    book_inserts = []
    post_book_inserts = DefaultDict(list)
    for book in am.books[start:end]:
        b_i, post_b_i = _get_book_insert_vals(book, schema)
        book_inserts.append(b_i)
        for sql_, vals in post_b_i.items():
            post_book_inserts[sql_].extend(vals)

    conn.executemany(sql.get_insert_book_sql(schema), book_inserts)
    for sql_, vals in post_book_inserts.items():
        conn.executemany(sql_, vals)


def _write_db(
    db_fn: Path,
    am: AllMetadata,
    schema: Schema,
    use_uuid_key: bool,
    user_sql_fn: Optional[Path],
) -> None:
    """Write all books and related data to the database."""
    if db_fn.is_file():
        logger.info("Overwriting existing database file '%s'.", db_fn)
        db_fn.unlink()

    logger.info("Creating '%s'.", db_fn)

    conn = connect(db_fn)
    try:
        with conn:
            conn.execute("PRAGMA foreign_keys=ON")
            _create_tables(conn, schema, use_uuid_key)
            _insert_sortdisplays(conn, am, schema)

            for start in range(0, len(am.books), _BATCH_SIZE):
                end = start + _BATCH_SIZE
                _insert_books_batch(conn, am, schema, start, end)
                num_books = min(len(am.books), end)
                logger.info(
                    "Inserted %s book%s into database.",
                    num_books,
                    "" if num_books == 1 else "s",
                )

        if user_sql_fn is not None:
            logger.info("Running user SQL file '%s'.", user_sql_fn)
            conn.executescript(read_text(user_sql_fn).strip())
    finally:
        conn.close()

    logger.info("Finished creating '%s'.", db_fn)


def _main(args: Namespace, _: Optional[list[str]] = None) -> None:
    """Main code for executing command."""
    o_dir = args.output_dir if args.output_dir else args.library_dirs[0]
    schema = read_schema(fn=args.schema, dirs=args.library_dirs)
    am = AllMetadata.from_args(
        args.library_dirs,
        args.dir_vars,
        schema,
        key_type=KeyType.UUID if args.use_uuid_key else KeyType.INT,
    )
    _write_db(get_db_fn(o_dir), am, schema, args.use_uuid_key, args.user_sql_file)


def get_cmd() -> Command:
    """Get Command."""
    _desc = """
    Create a SQLite database from book metadata. This command will overwrite an existing database
    file without asking for confirmation.
    """
    return Command(
        args=(
            Args.DIR_VARS,
            Args.LIBRARY_DIRS,
            Args.OUTPUT_DIR,
            Args.SCHEMA,
            Args.USER_SQL_FILE,
            Args.USE_UUID_KEY,
        ),
        cmd_name=CmdNames.DB,
        has_extra_args=False,
        main=_main,
        subparser_kwargs={
            "description": _desc,
            "help": "create a SQLite database from book metadata",
        },
    )
