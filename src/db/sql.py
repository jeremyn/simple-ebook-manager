"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Functions to get SQL statements.

"""
import textwrap

from src.util import Schema, SchemaItemTypes


def _fmt_sql(sql: str) -> str:
    """Format input sql."""
    return textwrap.dedent(sql).strip("\n")


def _coltype(use_uuid_key: bool) -> str:
    """Get column type."""
    return "TEXT" if use_uuid_key else "INT"


def _without_rowid(use_uuid_key: bool) -> str:
    """Get 'without rowid' text."""
    return " WITHOUT ROWID" if use_uuid_key else ""


def get_create_table_book_sql(schema: Schema, use_uuid_key: bool) -> str:
    """Get SQL to create table 'book'."""
    lines = [
        "CREATE TABLE book (",
        f"    pkey {_coltype(use_uuid_key)} PRIMARY KEY,",
        "    metadata_directory TEXT UNIQUE NOT NULL,",
    ]
    for item in schema:
        match item:
            case SchemaItemTypes.Date() | SchemaItemTypes.String():
                lines.append(f"    {item.name} TEXT,")
            case SchemaItemTypes.Title():
                lines.append(f"    {item.name}_sort TEXT UNIQUE NOT NULL,")
                lines.append(f"    {item.name}_display TEXT UNIQUE NOT NULL,")

    lines[-1] = lines[-1].rstrip(",")
    lines.append(f"){_without_rowid(use_uuid_key)}")
    return "\n".join(lines)


def get_insert_book_sql(schema: Schema) -> str:
    """Get SQL to insert a row into the book table."""
    fieldnames = ["pkey", "metadata_directory"]
    for item in schema:
        match item:
            case SchemaItemTypes.Date() | SchemaItemTypes.String():
                fieldnames.append(item.name)
            case SchemaItemTypes.Title():
                fieldnames.append(f"{item.name}_sort")
                fieldnames.append(f"{item.name}_display")

    return _fmt_sql(
        f"""
        INSERT INTO book (
            {", ".join(fieldnames)}
        ) VALUES (
            {", ".join([f":{fieldname}" for fieldname in fieldnames])}
        )
        """
    )


def get_create_table_book_file_sql(fieldname: str, use_uuid_key: bool) -> str:
    """Get SQL to create the file table."""
    return _fmt_sql(
        f"""
        CREATE TABLE book_{fieldname} (
            book_pkey {_coltype(use_uuid_key)} REFERENCES book(pkey),
            file_name TEXT UNIQUE NOT NULL,
            file_hash TEXT UNIQUE NOT NULL,
            file_full_path TEXT UNIQUE NOT NULL,
            metadata_directory TEXT NOT NULL,
            file_directory TEXT NOT NULL,
            dir_vars TEXT,
            PRIMARY KEY (book_pkey, file_name)
        ) WITHOUT ROWID
        """
    )


def get_insert_book_file_sql(fieldname: str) -> str:
    """Get SQL to insert a row into the file table."""
    return _fmt_sql(
        f"""
        INSERT INTO book_{fieldname} (
            book_pkey, file_name, file_hash, file_full_path,
            metadata_directory, file_directory, dir_vars
        ) VALUES (
            :book_pkey, :file_name, :file_hash, :file_full_path,
            :metadata_directory, :file_directory, :dir_vars
        )
        """
    )


def get_create_view_book_file_sql(fieldname: str, title_fieldname: str) -> str:
    """Get SQL to create view joining the book table with the file table."""
    return _fmt_sql(
        f"""
        CREATE VIEW v_book_{fieldname} AS
        SELECT
            cast(book.pkey || ':' || book_{fieldname}.file_name AS TEXT) AS unique_key,
            book.{title_fieldname}_sort AS {title_fieldname}_sort,
            book.{title_fieldname}_display AS {title_fieldname}_display,
            book_{fieldname}.file_name,
            book_{fieldname}.file_hash,
            book_{fieldname}.file_full_path,
            book_{fieldname}.metadata_directory,
            book_{fieldname}.file_directory,
            book_{fieldname}.dir_vars
        FROM
            book,
            book_{fieldname}
        WHERE
            book.pkey=book_{fieldname}.book_pkey
        ORDER BY
            book.{title_fieldname}_sort,
            book_{fieldname}.file_name
        """
    )


def get_create_table_keyvalue_sql(
    fieldname: str, key_label: str, value_label: str, use_uuid_key: bool
) -> str:
    """Get SQL to create a keyvalue table."""
    return _fmt_sql(
        f"""
        CREATE TABLE book_{fieldname} (
            book_pkey {_coltype(use_uuid_key)} REFERENCES book(pkey),
            {key_label} TEXT NOT NULL,
            {value_label} TEXT NOT NULL,
            PRIMARY KEY (book_pkey, {key_label})
        ) WITHOUT ROWID
        """
    )


def get_insert_keyvalue_sql(fieldname: str, key_label: str, value_label: str) -> str:
    """Get SQL to insert a row into a keyvalue table."""
    return _fmt_sql(
        f"""
        INSERT INTO book_{fieldname} (
            book_pkey, {key_label}, {value_label}
        ) VALUES (
            :book_pkey, :{key_label}, :{value_label}
        )
        """
    )


def get_create_view_keyvalue_sql(
    fieldname: str, key_label: str, value_label: str, title_fieldname: str
) -> str:
    """Get SQL to create view joining the book table to a keyvalue table."""
    return _fmt_sql(
        f"""
        CREATE VIEW v_book_{fieldname} AS
        SELECT
            cast(book.pkey || ':' || book_{fieldname}.{key_label} AS TEXT) AS unique_key,
            book.{title_fieldname}_sort AS {title_fieldname}_sort,
            book.{title_fieldname}_display AS {title_fieldname}_display,
            book_{fieldname}.{key_label},
            book_{fieldname}.{value_label}
        FROM
            book,
            book_{fieldname}
        WHERE
            book.pkey=book_{fieldname}.book_pkey
        ORDER BY
            book.{title_fieldname}_sort,
            book_{fieldname}.{key_label}
        """
    )


def get_create_table_sortdisplay_sql(fieldname: str, use_uuid_key: bool) -> str:
    """Get SQL to create a sortdisplay table."""
    return _fmt_sql(
        f"""
        CREATE TABLE {fieldname} (
            pkey {_coltype(use_uuid_key)} PRIMARY KEY,
            sort TEXT UNIQUE NOT NULL,
            display TEXT UNIQUE NOT NULL
        ){_without_rowid(use_uuid_key)}
        """
    )


def get_insert_sortdisplay_sql(fieldname: str) -> str:
    """Get SQL to insert a row into a sortdisplay table."""
    return _fmt_sql(
        f"""
        INSERT INTO {fieldname} (
            pkey, sort, display
        ) VALUES (
            :pkey, :sort, :display
        )
        """
    )


def get_create_view_sortdisplay_sql(fieldname: str, title_fieldname: str) -> str:
    """Get SQL to create view joining the book table to a sortdisplay table."""
    return _fmt_sql(
        f"""
        CREATE VIEW v_book_{fieldname} AS
        SELECT
            cast(book.pkey || ':' || {fieldname}.pkey AS TEXT) AS unique_key,
            book.{title_fieldname}_sort AS {title_fieldname}_sort,
            book.{title_fieldname}_display AS {title_fieldname}_display,
            {fieldname}.sort AS {fieldname}_sort,
            {fieldname}.display AS {fieldname}_display
        FROM
            book,
            book_{fieldname},
            {fieldname}
        WHERE
            book.pkey=book_{fieldname}.book_pkey AND
            book_{fieldname}.{fieldname}_pkey={fieldname}.pkey
        ORDER BY
            book.{title_fieldname}_sort,
            {fieldname}.sort
        """
    )


def get_create_table_sortdisplay_join_sql(fieldname: str, use_uuid_key: bool) -> str:
    """Get SQL to create a sortdisplay join table."""
    return _fmt_sql(
        f"""
        CREATE TABLE book_{fieldname} (
            book_pkey {_coltype(use_uuid_key)} REFERENCES book(pkey),
            {fieldname}_pkey {_coltype(use_uuid_key)} REFERENCES {fieldname}(pkey),
            PRIMARY KEY (book_pkey, {fieldname}_pkey)
        ) WITHOUT ROWID"""
    )


def get_insert_sortdisplay_join_sql(fieldname: str) -> str:
    """Get SQL to insert a row into a sortdisplay join table."""
    return _fmt_sql(
        f"""
        INSERT INTO book_{fieldname} (
            book_pkey, {fieldname}_pkey
        ) VALUES (
        :book_pkey, :{fieldname}_pkey
        )
        """
    )


def _get_create_view_summary_other_cte_sql(
    fieldname: str, col1: str, col2: str, delim: str
) -> str:
    """Get SQL for summary view CTE for file and keyvalue tables.

    group_concat can't be easily sorted in SQLite and its ordering is
    "arbitrary", see https://www.sqlite.org/lang_aggfunc.html#group_concat,
    so we use windowing functions to ensure correct ordering, see
    https://stackoverflow.com/a/57076660.

    """
    # pylint: disable=line-too-long
    return _fmt_sql(
        f"""
{fieldname}_concat AS (
    SELECT DISTINCT
        book_pkey,
        group_concat(book_{fieldname}_combined, ';') OVER (
            PARTITION BY
                book_pkey
            ORDER BY
                book_{fieldname}_combined
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS {fieldname}
    FROM (
        SELECT
            book.pkey AS book_pkey,
            book_{fieldname}.{col1} || '{delim}' || book_{fieldname}.{col2} AS book_{fieldname}_combined
        FROM
            book,
            book_{fieldname}
        WHERE
            book.pkey=book_{fieldname}.book_pkey
    )
),
    """
    )
    # pylint: enable=line-too-long


def _get_create_view_summary_sortdisplay_cte_sql(fieldname: str) -> str:
    """Get SQL for summary view CTE for sortdisplay tables.

    See comment about group_concat in _get_create_view_summary_other_cte_sql for relevant info.

    """
    return _fmt_sql(
        f"""
        {fieldname}_concat AS (
            SELECT DISTINCT
                book_pkey,
                group_concat({fieldname}_sort, ';') OVER (
                    PARTITION BY
                        book_pkey
                    ORDER BY
                        {fieldname}_sort
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS {fieldname}_sort,
                group_concat({fieldname}_display, ';') OVER (
                    PARTITION BY
                        book_pkey
                    ORDER BY
                        {fieldname}_display
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS {fieldname}_display
            FROM (
                SELECT
                    book.pkey AS book_pkey,
                    {fieldname}.sort AS {fieldname}_sort,
                    {fieldname}.display AS {fieldname}_display
                FROM
                    book,
                    book_{fieldname},
                    {fieldname}
                WHERE
                    book.pkey=book_{fieldname}.book_pkey AND
                    book_{fieldname}.{fieldname}_pkey={fieldname}.pkey
            )
        ),
        """
    )


def get_create_view_summary_sql(schema: Schema) -> str:
    """Get SQL to create summary view."""
    lines = ["CREATE VIEW v_summary AS\nWITH\n"]

    for item in schema:
        match item:
            case SchemaItemTypes.File():
                lines.append(
                    _get_create_view_summary_other_cte_sql(
                        item.name, "file_name", "file_hash", "::"
                    )
                    + "\n"
                )
            case SchemaItemTypes.KeyValue():
                lines.append(
                    _get_create_view_summary_other_cte_sql(
                        item.name, item.key_label, item.value_label, ":"
                    )
                    + "\n"
                )
            case SchemaItemTypes.SortDisplay():
                lines.append(
                    _get_create_view_summary_sortdisplay_cte_sql(item.name) + "\n"
                )

    lines[-1] = lines[-1].rstrip(",\n")
    lines.append("SELECT")
    lines.append("    book.pkey AS book_pkey,")
    lines.append("    book.metadata_directory,")

    for item in schema:
        match item:
            case SchemaItemTypes.Date() | SchemaItemTypes.String():
                lines.append(f"    book.{item.name},")
            case SchemaItemTypes.File() | SchemaItemTypes.KeyValue():
                lines.append(
                    f"    cast({item.name}_concat.{item.name} AS TEXT) AS {item.name},"
                )
            case SchemaItemTypes.SortDisplay():
                lines.append(
                    f"    cast({item.name}_concat.{item.name}_sort AS TEXT) AS {item.name}_sort,"
                )
                lines.append(
                    f"    cast({item.name}_concat.{item.name}_display AS TEXT) AS "
                    f"{item.name}_display,"
                )
            case SchemaItemTypes.Title():
                title_fieldname = item.name
                lines.append(f"    book.{title_fieldname}_sort,")
                lines.append(f"    book.{title_fieldname}_display,")

    lines[-1] = lines[-1].rstrip(",")
    lines.append(
        textwrap.dedent(
            """
        FROM
            book
            """
        )
    )

    for item in schema:
        if isinstance(
            item,
            (
                SchemaItemTypes.File,
                SchemaItemTypes.KeyValue,
                SchemaItemTypes.SortDisplay,
            ),
        ):
            lines.append(
                textwrap.dedent(
                    f"""
                LEFT OUTER JOIN
                    {item.name}_concat
                    ON
                    book.pkey={item.name}_concat.book_pkey
                    """
                )
            )

    lines.append(
        textwrap.dedent(
            f"""
        GROUP BY
            book.{title_fieldname}_sort
        ORDER BY
            book.{title_fieldname}_sort
            """
        )
    )

    return "\n".join([line.strip("\n") for line in lines])
