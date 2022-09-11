"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for working with files.

"""
import csv
import enum
import filecmp
import json
from pathlib import Path
from typing import Any, Optional, Sequence

from .misc import SimpleEbookManagerExit

JSONType = dict[str, Any]
_UTF_8 = "utf-8"


def cmp(fn1: Path, fn2: Path) -> bool:
    """Wrap filecmp.cmp to always use shallow=False.

    The default shallow=True can give inconsistently incorrect results.

    """
    return filecmp.cmp(fn1, fn2, shallow=False)


def get_csv_fn(dir_: Optional[Path], stem: str = "books") -> Path:
    """Get csv filename for dir_ and stem."""
    basename = f"{stem}.csv"
    return Path(basename) if dir_ is None else dir_ / basename


def get_db_fn(dir_: Path) -> Path:
    """Get db filename for dir_."""
    return dir_ / "books.sqlite3"


def get_metadata_fn(dir_: Path) -> Path:
    """Get metadata filename for dir_."""
    return dir_ / "metadata.json"


def get_schema_fn(dir_: Optional[Path]) -> Path:
    """Get schema filename for dir_."""
    basename = "schema.json"
    return Path(basename) if dir_ is None else dir_ / basename


def get_string_fn(dir_: Path, fieldname: str) -> Path:
    """Get text filename for dir_ and fieldname."""
    return dir_ / f"{fieldname}.txt"


class Newline(enum.Enum):
    """Represents the user-requested newline."""

    POSIX = "\n"
    WINDOWS = "\r\n"


def get_newline(newline_str: Optional[str], fn: Path) -> Newline:
    """Get newline, first from newline_str, else from fn."""
    if newline_str is not None:
        return Newline[newline_str.upper()]

    with Path(fn).open(encoding=_UTF_8) as file:
        file.readlines()

    try:
        newline = Newline(file.newlines)
    except ValueError:
        raise SimpleEbookManagerExit(
            f"ERROR: newline not specified and autodetect failed on '{fn}'."
        ) from None

    return newline


class _JSONDuplicateExit(SimpleEbookManagerExit):
    pass


def _error_if_duplicate_obj_keys(pairs: Sequence[tuple[str, str]]) -> dict[str, str]:
    """json.dumps object_pairs_hook to error if duplicate keys are found."""
    r_dict = {}
    for k, v in pairs:
        if k in r_dict:
            raise _JSONDuplicateExit(k)
        r_dict[k] = v
    return r_dict


def read_json(fn: Path) -> JSONType:
    """Read JSON from fn."""
    try:
        json_data: JSONType = json.loads(
            read_text(fn), object_pairs_hook=_error_if_duplicate_obj_keys
        )
    except _JSONDuplicateExit as exc:
        raise SimpleEbookManagerExit(
            f"ERROR: duplicate key '{exc.args[0]}' found in '{fn}'."
        ) from exc
    return json_data


def read_metadata(fn_or_dir: Path) -> dict[str, Any]:
    """Read metadata from input fn_or_dir."""
    return (
        read_json(get_metadata_fn(fn_or_dir))
        if fn_or_dir.is_dir()
        else read_json(fn_or_dir)
    )


def read_text(fn: Path) -> str:
    """Read text from fn."""
    return fn.read_text(encoding=_UTF_8)


def write_csv(fn: Path, rows: Sequence[dict[str, str]]) -> None:
    """Write rows to CSV file fn."""
    with fn.open(mode="w", encoding=_UTF_8, newline="") as file:
        writer = csv.DictWriter(file, rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def write_json(
    fn: Path,
    data: Any,
    *,
    newline: Newline = Newline.POSIX,
    custom_kw: Optional[dict[str, Any]] = None,
) -> None:
    """Write standardized JSON. custom_kw will overwrite default kwargs."""
    json_kw: dict[str, Any] = {"ensure_ascii": False, "indent": 4, "sort_keys": True}
    if custom_kw is not None:
        json_kw.update(custom_kw)
    write_text(fn, json.dumps(data, **json_kw), newline=newline)


def write_schema(fn: Path, data: JSONType) -> None:
    """Write schema JSON to fn."""
    write_json(fn, data, custom_kw={"sort_keys": False})


def write_text(fn: Path, text: str, *, newline: Newline = Newline.POSIX) -> None:
    """Write standardized text to fn.

    Newline reference: https://docs.python.org/3/library/functions.html#open

    """
    with fn.open(mode="w", encoding=_UTF_8, newline=newline.value) as file:
        file.write(text.rstrip("\n") + "\n")
