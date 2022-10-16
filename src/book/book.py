"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for Book.

The Unicode/ASCII replacement logic is in the _replace_unicode function.

"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

from src.util import (
    DirVars,
    Newline,
    Schema,
    SchemaItemTypes,
    SimpleEbookManagerException,
    SimpleEbookManagerExit,
    get_metadata_fn,
    get_string_fn,
    read_metadata,
    read_text,
    write_json,
    write_text,
)

from .date import BookDate
from .file import BookFile
from .keyvalue import BookKeyValue
from .sortdisplay import SortDisplay


class _BookJSONEncoder(json.JSONEncoder):
    """Encoder to write a book's metadata JSON."""

    def __init__(self, schema: Schema, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._schema = schema

    def default(self, o: Any) -> Any:
        if isinstance(o, Book):
            book = o
            r_val: dict[str, Any] = {}
            for item in self._schema:
                match item:
                    case SchemaItemTypes.Date():
                        r_val[item.name] = (
                            date_val.as_str(item.input_format)
                            if (date_val := book.fields.dates[item.name]) is not None
                            else None
                        )

                    case SchemaItemTypes.File():
                        files_val = [
                            {
                                "directory": file.input_dir_str,
                                "hash": file.hash,
                                "name": file.basename,
                            }
                            for file in book.files
                        ]
                        r_val[item.name] = (
                            files_val[0] if len(files_val) == 1 else files_val
                        )

                    case SchemaItemTypes.KeyValue():
                        r_val[item.name] = (
                            {i.key: i.value for i in kv_val}
                            if (kv_val := book.fields.keyvalues[item.name])
                            else None
                        )

                    case SchemaItemTypes.SortDisplay():
                        sd_inputs = [
                            sd.display
                            if sd.display == sd.sort
                            else {"display": sd.display, "sort": sd.sort}
                            for sd in book.fields.sortdisplays[item.name]
                        ]
                        if len(sd_inputs) == 0:
                            r_val[item.name] = None
                        elif len(sd_inputs) == 1:
                            r_val[item.name] = sd_inputs[0]
                        else:
                            r_val[item.name] = sd_inputs

                    case SchemaItemTypes.String() if item.inline:
                        r_val[item.name] = book.fields.strings[item.name]
                    case SchemaItemTypes.Title():
                        r_val[item.name] = (
                            book.title.display
                            if book.title.display == book.title.sort
                            else {
                                "display": book.title.display,
                                "sort": book.title.sort,
                            }
                        )

            return dict(sorted(r_val.items()))

        return super().default(o)


def _remove_whitespace(text: str) -> str:
    """Remove whitespace from beginning and end of lines."""
    return "\n".join([line.strip() for line in text.split("\n")])


def _replace_unicode(text: str) -> str:
    """Replace specific Unicode symbols."""
    return (
        # em dash with whitespace
        re.sub(r"(\w)—(\w)", r"\g<1> -- \g<2>", text)
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("…", "...")
        .replace("•", "*")
        # en dash
        .replace("–", "-")
        # em dash
        .replace("—", "--")
    )


@dataclass(frozen=True)
class _BookFields:
    """Book fields."""

    dates: dict[str, Optional[BookDate]]
    keyvalues: dict[str, Sequence[BookKeyValue]]
    sortdisplays: dict[str, Sequence[SortDisplay]]
    strings: dict[str, Optional[str]]


def _get_date(dt_input: Optional[str], input_fmt: str) -> Optional[BookDate]:
    """Get BookDate."""
    return BookDate.from_args(dt_input, input_fmt) if dt_input is not None else None


def _get_files(
    f_inputs: dict[str, str] | Sequence[dict[str, str]],
    book_title_sort: str,
    metadata_dir: Path,
    dir_vars: DirVars,
) -> Sequence[BookFile]:
    """Get BookFiles and check for duplicates."""
    if isinstance(f_inputs, dict):
        f_inputs = [f_inputs]

    files: list[BookFile] = []
    basenames: list[str] = []
    for f_dict in sorted(f_inputs, key=lambda fd: fd["name"]):
        match f_dict:
            case {"directory": input_dir_str, "name": basename, "hash": hash_}:
                pass
            case {"name": basename, "hash": hash_}:
                input_dir_str = "."
            case _:
                raise SimpleEbookManagerException(f"invalid f_dict: {f_dict}")

        if basename in basenames:
            raise SimpleEbookManagerExit(
                f"ERROR: duplicate file with name '{basename}' found in "
                f"'{get_metadata_fn(metadata_dir)}'."
            ) from None
        basenames.append(basename)

        files.append(
            BookFile.from_args(
                book_title_sort, basename, metadata_dir, dir_vars, input_dir_str, hash_
            )
        )

    return tuple(files)


def _get_keyvalues(
    kvs_input: Optional[dict[str, Optional[str]]], fieldname: str, metadata_dir: Path
) -> Sequence[BookKeyValue]:
    """Get BookKeyValues and check for null values."""
    keyvalues = []
    if kvs_input is not None:
        for k, v in sorted(kvs_input.items()):
            if v is None:
                raise SimpleEbookManagerExit(
                    f"ERROR: key '{k}' in keyvalue field '{fieldname}' in "
                    f"'{get_metadata_fn(metadata_dir)}' has a null value."
                )
            keyvalues.append(BookKeyValue(k, v))

    return tuple(keyvalues)


def _get_sortdisplays(
    sd_inputs: Optional[str | dict[str, str] | Sequence[str | dict[str, str]]],
    d_type: str,
    metadata_dir: Path,
) -> Sequence[SortDisplay]:
    """Expand inputs to SortDisplays and checks for duplicates."""
    if sd_inputs is None:
        sd_inputs = []
    elif isinstance(sd_inputs, str | dict):
        sd_inputs = [sd_inputs]

    sds = []
    sorts = []
    displays = []
    for sd_input in sd_inputs:
        match sd_input:
            case str(sort):
                sd = SortDisplay(sort, sort)
            case {"display": display, "sort": sort}:
                sd = SortDisplay(sort, display)
            case _:
                raise SimpleEbookManagerException(f"invalid sd_input: {sd_input}")

        if sd.sort in sorts:
            raise SimpleEbookManagerExit(
                f"ERROR: duplicate '{d_type}' data 'sort={sd.sort}' found in "
                f"'{get_metadata_fn(metadata_dir)}'."
            ) from None
        sorts.append(sd.sort)

        if sd.display in displays:
            raise SimpleEbookManagerExit(
                f"ERROR: duplicate '{d_type}' data 'display={sd.display}' found in "
                f"'{get_metadata_fn(metadata_dir)}'."
            ) from None
        displays.append(sd.display)

        sds.append(sd)

    return tuple(sorted(sds))


def _get_string(
    metadata: dict[str, Optional[str]],
    item: SchemaItemTypes.String,
    metadata_dir: Path,
    title_prefix: str,
) -> Optional[str]:
    """Get string value from metadata if inline or text file otherwise."""
    if item.inline:
        return metadata[item.name]

    if item.name in metadata:
        raise SimpleEbookManagerExit(
            f"ERROR: '{item.name}' data found in '{get_metadata_fn(metadata_dir)}' but field "
            "is inline: false in the schema."
        )
    fn = get_string_fn(metadata_dir, item.name)
    return read_text(fn).removeprefix(title_prefix) if fn.is_file() else None


def _str_title_prefix(display: str) -> str:
    """Get prefix for non-inline string text files."""
    return f"# Title: {display}\n#\n"


@dataclass(order=True)
class Book:
    """Represents a single real-world book matching a book dir."""

    title: SortDisplay
    metadata_dir: Path
    fields: _BookFields
    files: Sequence[BookFile]

    @property
    def str_title_prefix(self) -> str:
        """Get prefix for non-inline string text files."""
        return _str_title_prefix(self.title.display)

    def write_metadata(
        self,
        o_dir: Path,
        schema: Schema,
        *,
        newline: Newline = Newline.POSIX,
        replace_unicode: bool = False,
    ) -> Sequence[Path]:
        """Write metadata for this book and return written filenames."""
        metadata_fn = get_metadata_fn(o_dir)
        write_json(
            get_metadata_fn(o_dir),
            self,
            newline=newline,
            custom_kw={"cls": _BookJSONEncoder, "schema": schema},
        )
        output_fns = [metadata_fn]

        for item in schema:
            if (
                isinstance(item, SchemaItemTypes.String)
                and not item.inline
                and (s_val := self.fields.strings[item.name]) is not None
            ):
                s_val = _remove_whitespace(s_val)
                if replace_unicode:
                    s_val = _replace_unicode(s_val)
                string_fn = get_string_fn(o_dir, item.name)
                write_text(string_fn, self.str_title_prefix + s_val, newline=newline)
                output_fns.append(string_fn)
        return output_fns

    @classmethod
    def from_args(cls, b_dir: Path, dir_vars: DirVars, schema: Schema) -> "Book":
        """Get Book from args."""
        metadata_dir = b_dir.resolve()
        dir_vars = tuple(sorted(dir_vars))
        metadata_fn = get_metadata_fn(metadata_dir)
        metadata = read_metadata(metadata_fn)

        title = _get_sortdisplays(
            metadata[schema.title_fieldname], schema.title_fieldname, metadata_dir
        )[0]
        fields = _BookFields({}, {}, {}, {})
        for item in schema:
            match item:
                case SchemaItemTypes.Date():
                    fields.dates[item.name] = _get_date(
                        metadata[item.name], item.input_format
                    )
                case SchemaItemTypes.File():
                    files = _get_files(
                        metadata[item.name], title.sort, metadata_dir, dir_vars
                    )
                case SchemaItemTypes.KeyValue():
                    fields.keyvalues[item.name] = _get_keyvalues(
                        metadata[item.name], item.name, metadata_dir
                    )
                case SchemaItemTypes.SortDisplay():
                    fields.sortdisplays[item.name] = _get_sortdisplays(
                        metadata[item.name], item.name, metadata_dir
                    )
                case SchemaItemTypes.String():
                    fields.strings[item.name] = _get_string(
                        metadata,
                        item,
                        metadata_dir,
                        _str_title_prefix(title.display),
                    )

        return cls(title, metadata_dir, fields, files)
