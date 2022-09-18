"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for clean command.

"""
import logging
import shutil
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Sequence

from src.all_metadata import AllMetadata, KeyType
from src.book import Book, BookFile
from src.command import Args, CmdNames, Command
from src.util import (
    Algorithm,
    Newline,
    Schema,
    SimpleEbookManagerException,
    SimpleEbookManagerExit,
    cmp,
    get_file_hashes,
    get_metadata_fn,
    get_newline,
    read_schema,
)

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100


def _get_algo(algo_str: Optional[str], bookfile: BookFile) -> Optional[Algorithm]:
    """Get Algorithm.

    Return None if algo_str is None, else Algorithm from algo_str if it's not "autodetect", else
    detect Algorithm from bookfile.

    """
    if algo_str is None:
        return None

    try:
        return Algorithm[algo_str.upper()]
    except KeyError:
        pass

    if algo_str == "autodetect":
        try:
            return Algorithm[bookfile.hash.split(":")[0].upper()]
        except KeyError:
            raise SimpleEbookManagerExit(
                f"ERROR: '{Args.UPDATE_HASH.opt}' provided without algorithm and autodetect failed "
                f"on the hash for '{bookfile.basename}' in "
                f"'{get_metadata_fn(bookfile.metadata_dir)}'."
            ) from None

    raise SimpleEbookManagerException(f"invalid algo_str: '{algo_str}'")


def _update_files_if_changed(book: Book, output_fns: Sequence[Path]) -> bool:
    """Replace metadata files from t_dir if the files have changed."""
    changes_found = False
    for fn in output_fns:
        if not cmp(fn, (orig_fn := book.metadata_dir / fn.name)):
            changes_found = True
            shutil.move(fn, orig_fn)
            logger.info("'%s': file changed.", orig_fn)
    return changes_found


def _clean(
    am: AllMetadata,
    schema: Schema,
    newline: Newline,
    algo: Optional[Algorithm],
    replace_unicode: bool,
) -> None:
    """Update metadata files for each book as appropriate."""
    if algo is not None:
        logger.info("Calculating file hashes.")
        hashes = dict(get_file_hashes([f.fn for f in am.files], algo))
        logger.info("Done calculating file hashes.")

    logger.info("Starting processing.")

    i = 0
    changes_found = False
    for i, book in enumerate(am.books, start=1):
        if algo is not None:
            for file in book.files:
                if (calc_hash := hashes[file.fn]) != file.hash:
                    logger.info(
                        (
                            "'%s': hash mismatch: calculated: '%s', hash in metadata file: '%s', "
                            "metadata file: '%s'."
                        ),
                        file.fn,
                        calc_hash,
                        file.hash,
                        get_metadata_fn(file.metadata_dir),
                    )
                    file.hash = calc_hash

        with TemporaryDirectory() as t_dir_str:
            t_dir = Path(t_dir_str)
            fns = book.write_metadata(
                t_dir, schema, newline=newline, replace_unicode=replace_unicode
            )
            changes_found = _update_files_if_changed(book, fns) or changes_found

        if not i % _BATCH_SIZE:
            logger.info("Processed %s book%s.", i, "" if i == 1 else "s")

    if len(am.books) % _BATCH_SIZE:
        logger.info(
            "Processed %s book%s.", len(am.books), "" if len(am.books) == 1 else "s"
        )

    logger.info(
        "Finished processing, changes made!"
        if changes_found
        else "Finished processing, no changes needed."
    )


def _main(args: Namespace, _: Optional[list[str]] = None) -> None:
    """Main code for executing command."""
    schema = read_schema(fn=args.schema, dirs=args.library_dirs)
    am = AllMetadata.from_args(
        args.library_dirs, args.dir_vars, schema, key_type=KeyType.NONE
    )

    _clean(
        am,
        schema,
        get_newline(args.newline, get_metadata_fn(am.books[0].metadata_dir)),
        _get_algo(args.update_hash, am.files[0]),
        args.replace_unicode,
    )


def get_cmd() -> Command:
    """Get Command."""
    _desc = """
    Clean metadata and associated text files by standardizing whitespace and layout, adding headers, 
    replacing certain Unicode symbols and more. Optionally update MD5/SHA256 hashes for book files.
    """
    return Command(
        args=(
            Args.DIR_VARS,
            Args.LIBRARY_DIRS,
            Args.NEWLINE,
            Args.REPLACE_UNICODE,
            Args.SCHEMA,
            Args.UPDATE_HASH,
        ),
        cmd_name=CmdNames.CLEAN,
        has_extra_args=False,
        main=_main,
        subparser_kwargs={
            "description": _desc,
            "help": "clean metadata and associated text files",
        },
    )
