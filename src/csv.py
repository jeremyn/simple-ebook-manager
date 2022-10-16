"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Create one or more CSV files for books.

"""
import logging
from argparse import Namespace
from pathlib import Path
from typing import Optional, Sequence

from src.all_metadata import AllMetadata, KeyType
from src.book import BookFile, SortDisplay
from src.command import Args, CmdNames, Command
from src.util import Schema, SchemaItemTypes, get_csv_fn, read_schema, write_csv

logger = logging.getLogger(__name__)

_DELIM = ";"
_ORD_OFFSET = ord("A") - 1


def _get_file_key(book_title_key: str, basename: str) -> str:
    """Get a standard lookup key for files."""
    return "|".join([book_title_key, basename])


def _get_vlookup(
    sheetname: str, key: str, num_all_rows: int, num_all_cols: int, colname: str
) -> str:
    """Get a VLOOKUP/MATCH string."""
    try:
        int(key)
    except ValueError:
        key = f'"{key}"'

    endcolchr = chr(num_all_cols + _ORD_OFFSET)
    table_range = f"{sheetname}!A2:{sheetname}!{endcolchr}{num_all_rows + 1}"
    match = f'MATCH("{colname}",{sheetname}!A1:{sheetname}!{chr(num_all_cols + _ORD_OFFSET)}1,0)'
    return f"VLOOKUP({key},{table_range},{match},FALSE)"


def _get_csv_output_string(
    fieldname: str, items: Sequence[SortDisplay], num_all_rows: int, colname: str
) -> str:
    """Get a CONCATENATE string."""
    if len(items) == 0:
        return ""

    vlookups = [
        _get_vlookup(
            fieldname,
            item.key,
            num_all_rows,
            len(("key", "_sort", "_display")),
            colname,
        )
        for item in items
    ]

    return (
        f"={vlookups[0]}"
        if len(vlookups) == 1
        else "=CONCATENATE(" + f', "{_DELIM}", '.join(vlookups) + ")"
    )


def _get_files_str(
    files: Sequence[BookFile],
    book_title_key: str,
    num_all_files: int,
    num_file_cols: int,
    files_fieldname: str,
) -> str:
    """Get the files string for a book."""
    files_str = "=CONCATENATE("
    parts: list[str] = []
    for file in files:
        vlookup = _get_vlookup(
            files_fieldname,
            _get_file_key(book_title_key, file.basename),
            num_all_files,
            num_file_cols,
            "file_hash",
        )
        parts.append(f'"{file.basename}::", {vlookup}')
    files_str += f', "{_DELIM}", '.join(parts)
    files_str += ")"
    return files_str


def _get_book_colnames(schema: Schema, split: bool) -> Sequence[str]:
    """Get column names for the main book CSV."""
    colnames = ["key"] if split else []
    colnames.append("metadata_directory")
    for item in schema:
        if isinstance(item, SchemaItemTypes.SortDisplay | SchemaItemTypes.Title):
            colnames.append(f"{item.name}_sort")
            colnames.append(f"{item.name}_display")
        else:
            colnames.append(item.name)
    return tuple(colnames)


def _get_book_rows(
    am: AllMetadata,
    schema: Schema,
    colnames: Sequence[str],
    num_file_cols: int,
    split: Optional[bool],
) -> Sequence[dict[str, str]]:
    """Get all rows for the main book CSV."""
    rows = []
    for book in am.books:
        colvals = [book.title.key] if split else []
        colvals.append(str(book.metadata_dir))
        for item in schema:
            match item:
                case SchemaItemTypes.Date():
                    colvals.append(
                        date_val.as_str(item.output_format)
                        if (date_val := book.fields.dates[item.name]) is not None
                        else ""
                    )

                case SchemaItemTypes.File():
                    if split:
                        files_str = _get_files_str(
                            book.files,
                            book.title.key,
                            len(am.files),
                            num_file_cols,
                            item.name,
                        )
                    else:
                        files_str = _DELIM.join(
                            [f"{f.basename}::{f.hash}" for f in book.files]
                        )
                    colvals.append(files_str)

                case SchemaItemTypes.KeyValue():
                    colvals.append(
                        _DELIM.join(
                            [
                                f"{kv.key}:{kv.value}"
                                for kv in book.fields.keyvalues[item.name]
                            ]
                        )
                    )

                case SchemaItemTypes.SortDisplay():
                    sortdisplays = book.fields.sortdisplays[item.name]
                    if split:
                        colvals.append(
                            _get_csv_output_string(
                                item.name,
                                sortdisplays,
                                len(am.fields[item.name]),
                                f"{item.name}_sort",
                            )
                        )
                        colvals.append(
                            _get_csv_output_string(
                                item.name,
                                sortdisplays,
                                len(am.fields[item.name]),
                                f"{item.name}_display",
                            )
                        )
                    else:
                        colvals.append(_DELIM.join([sd.sort for sd in sortdisplays]))
                        colvals.append(_DELIM.join([sd.display for sd in sortdisplays]))

                case SchemaItemTypes.String():
                    colvals.append(
                        string_val
                        if (string_val := book.fields.strings[item.name]) is not None
                        else ""
                    )

                case SchemaItemTypes.Title():
                    colvals.append(book.title.sort)
                    colvals.append(book.title.display)

        rows.append(dict(zip(colnames, colvals, strict=True)))

    return rows


def _get_file_colnames(schema: Schema) -> Sequence[str]:
    """Get column names for the file CSV."""
    return (
        "key",
        f"{schema.title_fieldname}_sort",
        f"{schema.title_fieldname}_display",
        "file_name",
        "file_hash",
        "file_full_path",
        "metadata_directory",
        "file_directory",
        "dir_vars",
    )


def _get_file_rows(
    am: AllMetadata, colnames: Sequence[str], num_book_cols: int, books_sheetname: str
) -> Sequence[dict[str, str]]:
    """Get all rows for the file CSV."""
    key_map = {book.title.sort: book.title.key for book in am.books}
    rows = []
    for file in am.files:
        book_title_key = key_map[file.book_title_sort]
        colvals = [
            _get_file_key(book_title_key, file.basename),
            "="
            + _get_vlookup(
                books_sheetname,
                book_title_key,
                len(am.books),
                num_book_cols,
                colnames[1],
            ),
            "="
            + _get_vlookup(
                books_sheetname,
                book_title_key,
                len(am.books),
                num_book_cols,
                colnames[2],
            ),
            file.basename,
            file.hash,
            str(file.fn),
            str(file.metadata_dir),
            file.input_dir_str,
            _DELIM.join([str(dir_var) for dir_var in file.dir_vars]),
        ]
        rows.append(dict(zip(colnames, colvals, strict=True)))

    return rows


def _log_writing(csv_fn: Path) -> None:
    """Log a standard message when writing csv_fn."""
    if csv_fn.is_file():
        logger.info("Overwriting existing CSV file '%s'.", csv_fn)
    else:
        logger.info("Creating '%s'.", csv_fn)


def _write_csvs(output_dir: Path, am: AllMetadata, schema: Schema, split: bool) -> None:
    """Write one or more CSV files."""
    book_colnames = _get_book_colnames(schema, split)
    file_colnames = _get_file_colnames(schema)

    books_fn = get_csv_fn(output_dir)
    book_rows = _get_book_rows(am, schema, book_colnames, len(file_colnames), split)
    _log_writing(books_fn)
    write_csv(books_fn, book_rows)
    logger.info(
        "Wrote %s book%s to file.", len(book_rows), "" if len(book_rows) == 1 else "s"
    )

    csv_files = [books_fn]
    if split:
        for item in schema:
            rows = None
            match item:
                case SchemaItemTypes.File():
                    rows = _get_file_rows(
                        am, file_colnames, len(book_colnames), books_fn.stem
                    )
                case SchemaItemTypes.SortDisplay():
                    rows = [
                        {
                            "key": sd.key,
                            f"{item.name}_sort": sd.sort,
                            f"{item.name}_display": sd.display,
                        }
                        for sd in am.fields[item.name]
                    ]

            if rows is not None:
                csv_fn = get_csv_fn(output_dir, item.name)
                csv_files.append(csv_fn)
                _log_writing(csv_fn)
                write_csv(csv_fn, rows)

    if len(csv_files) == 1:
        logger.info("Finished writing CSV file.")
    else:
        logger.info("Finished writing %s CSV files.", len(csv_files))


def _main(args: Namespace, _: Optional[list[str]] = None) -> None:
    """Main code for executing command."""
    output_dir = args.output_dir if args.output_dir else args.library_dirs[0]
    schema = read_schema(fn=args.schema, dirs=args.library_dirs)
    am = AllMetadata.from_args(
        args.library_dirs,
        args.dir_vars,
        schema,
        key_type=KeyType.UUID if args.use_uuid_key else KeyType.INT,
    )
    _write_csvs(output_dir, am, schema, args.split)


def get_cmd() -> Command:
    """Get Command."""
    _desc = f"""
    Create one or more CSV files from book metadata. By default, a single '{get_csv_fn(None)}' file
    will be created. With the `{Args.SPLIT.opt}` option, multiple CSV files will be created that
    can be added as different worksheets in the same spreadsheet, with each worksheet named after
    the corresponding CSV file. This command will overwrite existing output files without asking
    for confirmation.
    """
    return Command(
        args=(
            Args.DIR_VARS,
            Args.LIBRARY_DIRS,
            Args.OUTPUT_DIR,
            Args.SPLIT,
            Args.SCHEMA,
            Args.USE_UUID_KEY,
        ),
        cmd_name=CmdNames.CSV,
        has_extra_args=False,
        main=_main,
        subparser_kwargs={
            "description": _desc,
            "help": "create one or more CSV files from book metadata",
        },
    )
