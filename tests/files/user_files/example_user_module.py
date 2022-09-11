"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Example user module to pass to custom command.

The important thing is to have a `process` function with the same signature as below.

"""
import filecmp
import logging
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Sequence

logger = logging.getLogger(__name__)

DESC_BASENAME = "description.txt"
METADATA_BASENAME = "metadata.json"

FIELDNAME = "example_user_module_str_func_name"


def _update_desc_file(
    book_dir: Path, temp_dir: Path, str_func_name: str, funcs: SimpleNamespace
) -> bool:
    """Update description file, return whether file was changed."""
    desc_fn = book_dir / DESC_BASENAME
    if not desc_fn.is_file():
        return False

    temp_desc_fn = temp_dir / DESC_BASENAME
    str_func = getattr(str, str_func_name)

    desc_lines = funcs.read_text(desc_fn).splitlines()
    if desc_lines[0].startswith("# Title: "):
        desc_text = "\n".join(
            desc_lines[:2] + [str_func(line) for line in desc_lines[2:]]
        )
    else:
        desc_text = "\n".join([str_func(line) for line in desc_lines])

    funcs.write_text(temp_desc_fn, desc_text)

    if book_modified := not filecmp.cmp(temp_desc_fn, desc_fn, shallow=False):
        shutil.move(temp_desc_fn, desc_fn)

    return book_modified


def _update_metadata_file(
    book_dir: Path, temp_dir: Path, str_func_name: str, funcs: SimpleNamespace
) -> bool:
    """Update metadata file, return whether file was changed."""
    metadata_fn = book_dir / METADATA_BASENAME
    temp_metadata_fn = temp_dir / METADATA_BASENAME

    metadata = funcs.read_json(metadata_fn)
    metadata[FIELDNAME] = str_func_name
    funcs.write_json(temp_metadata_fn, metadata)

    if book_modified := not filecmp.cmp(temp_metadata_fn, metadata_fn, shallow=False):
        shutil.move(temp_metadata_fn, metadata_fn)

    return book_modified


def process(
    book_dirs: Sequence[Path], extra_args: list[str], funcs: SimpleNamespace
) -> None:
    """Example process function to use with custom command.

    The user module you pass to the custom command should have a `process` method with this
    signature:

    * book_dirs: book dirs found in library dirs provided to custom command
    * extra_args: command-line args that custom command couldn't identify so has passed here
    * funcs: a collection of helper functions to read and write files: read_json, write_json,
        read_text and write_text
    * returns None

    This example either lower- or uppercases the description file (except for the title prefix if
    present) based on user input, adds/modifies a field in the metadata file to have the value
    "lower" or "upper", then at the end reports how many books have been modified.

    The complete command for running this custom process should be similar to:
        ebooks custom --library-dirs $DIRS --user-module $THIS_FILE --case-to {lower,upper}

    In your own code your options can have any names you want as long as they don't conflict with
    the existing options listed with `ebooks custom --help`.

    """
    case_to_arg = "--case-to"
    allowed = ["lower", "upper"]
    if (
        case_to_arg in extra_args[:-1]
        and (extra_args[extra_args.index(case_to_arg) + 1]) in allowed
    ):
        str_func_name = extra_args[extra_args.index(case_to_arg) + 1]
    else:
        raise SystemExit(
            f"ERROR: usage requires '{case_to_arg} {{{','.join(allowed)}}}'."
        )

    num_books_modified = 0
    for book_dir in book_dirs:
        logger.info("Processing '%s'.", str(book_dir))
        with TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)
            desc_modified = _update_desc_file(book_dir, temp_dir, str_func_name, funcs)
            metadata_modified = _update_metadata_file(
                book_dir, temp_dir, str_func_name, funcs
            )
            if desc_modified or metadata_modified:
                num_books_modified += 1

    logger.info(
        "Modified %s book%s.",
        num_books_modified,
        "" if num_books_modified == 1 else "s",
    )
