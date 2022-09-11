"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for AllMetadata.

"""
import enum
import logging
import uuid
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import DefaultDict, Optional, Sequence

from src.book import Book, BookFile, SortDisplay
from src.util import DirVars, Schema, SimpleEbookManagerExit, get_metadata_fn

logger = logging.getLogger(__name__)


class KeyType(enum.Enum):
    """Which type of key to assign in AllMetadata."""

    INT = enum.auto()
    NONE = enum.auto()
    UUID = enum.auto()


def get_all_book_dirs(l_dirs: Sequence[Path]) -> Sequence[Path]:
    """Get all book dirs from the given top level library dirs.

    Returned book dirs should keep l_dirs input order but be sorted within each l_dir.

    """
    all_b_dirs = []
    for l_dir in l_dirs:
        if get_metadata_fn(l_dir).is_file():
            raise SimpleEbookManagerExit(
                (
                    f"ERROR: specified library dir '{l_dir}' has a "
                    f"'{get_metadata_fn(l_dir).name}' file and might be a book directory."
                )
            )

        all_b_dirs.extend(
            [
                item
                for item in sorted(l_dir.glob("[!.]*"))
                if get_metadata_fn(item).is_file()
            ]
        )

    if not all_b_dirs:
        raise SimpleEbookManagerExit("ERROR: no book directories found.")

    return tuple(all_b_dirs)


def _get_books(
    b_dirs: Sequence[Path], dir_vars: DirVars, schema: Schema
) -> Sequence[Book]:
    """Get books from b_dirs and check for duplicates."""
    titles = []
    displays = []
    sorts = []
    books = []
    for b_dir in b_dirs:
        book = Book.from_args(b_dir, dir_vars, schema)
        if book.title in titles:
            raise SimpleEbookManagerExit(
                f"ERROR: the title with sort '{book.title.sort}' and display "
                f"'{book.title.display}' appears in more than one book."
            )
        titles.append(book.title)

        if book.title.display in displays:
            raise SimpleEbookManagerExit(
                f"ERROR: the title display value '{book.title.display}' has more than one sort "
                "value over all books."
            )
        displays.append(book.title.display)

        if book.title.sort in sorts:
            raise SimpleEbookManagerExit(
                f"ERROR: the title sort value '{book.title.sort}' has more than one display value "
                "over all books."
            )
        sorts.append(book.title.sort)

        books.append(book)

    return tuple(sorted(books))


def _sd_error_duplicate(fieldname: str, type_: str, val: str) -> None:
    """Raise error for partial duplicate sortdisplays."""
    other_type = "display" if type_ == "sort" else "sort"
    raise SimpleEbookManagerExit(
        f"ERROR: for field '{fieldname}' the {type_} value '{val}' has more than one {other_type} "
        "value over all books."
    )


_SDDicts = dict[str, dict[SortDisplay, SortDisplay]]


def _get_sd_dicts(books: Sequence[Book], key_type: KeyType) -> _SDDicts:
    """Get SortDisplays from books, assign keys and check for duplicates."""
    sd_sets: dict[str, set[SortDisplay]] = DefaultDict(set)

    for book in books:
        for fieldname, sds in book.fields.sortdisplays.items():
            sd_sets[fieldname] |= set(sds)

    sd_dicts: _SDDicts = DefaultDict(dict)
    for fieldname, sd_set in sd_sets.items():
        displays = sorted([sd.display for sd in sd_set])
        for i in range(len(displays) - 1):
            if displays[i] == displays[i + 1]:
                _sd_error_duplicate(fieldname, "display", displays[i])

        sd_list = sorted(sd_set)
        for i, sd in enumerate(sd_list):
            if (i < (len(sd_list) - 1)) and (sd.sort == sd_list[i + 1].sort):
                _sd_error_duplicate(fieldname, "sort", sd.sort)

            key: Optional[str]
            match key_type:
                case KeyType.INT:
                    key = str(i + 1)
                case KeyType.NONE:
                    key = None
                case KeyType.UUID:
                    key = str(uuid.uuid4())

            sd_dicts[fieldname][sd] = SortDisplay(sd.sort, sd.display, key)

    return sd_dicts


def _get_books_with_keys(
    books_no_keys: Sequence[Book], sd_dicts: _SDDicts, key_type: KeyType
) -> Sequence[Book]:
    """Add keys to books."""
    books_with_keys = []
    for i, book in enumerate(books_no_keys):
        book.title = SortDisplay(
            sort=book.title.sort,
            display=book.title.display,
            _key=str(uuid.uuid4()) if key_type == KeyType.UUID else str(i + 1),
        )
        for fieldname, sds_no_key in book.fields.sortdisplays.items():
            if sds_no_key is not None:
                book.fields.sortdisplays[fieldname] = tuple(
                    sd_dicts[fieldname][sd] for sd in sds_no_key
                )
        books_with_keys.append(book)

    return tuple(books_with_keys)


AMFields = dict[str, Sequence[SortDisplay]]


@dataclass(frozen=True)
class AllMetadata:
    """All books and data extracted from books."""

    books: Sequence[Book]
    fields: AMFields
    files: Sequence[BookFile]

    @classmethod
    def from_args(
        cls,
        l_dirs: Sequence[Path],
        dir_vars: DirVars,
        schema: Schema,
        *,
        key_type: KeyType,
    ) -> "AllMetadata":
        """Get AllMetadata from args."""
        if key_type == KeyType.NONE:
            logger.info("Collecting book data.")
        else:
            logger.info(
                "Collecting book data and assigning %s keys.",
                "UUID" if key_type == KeyType.UUID else "integer",
            )

        books_no_keys = _get_books(get_all_book_dirs(l_dirs), dir_vars, schema)
        sd_dicts = _get_sd_dicts(books_no_keys, key_type)

        return cls(
            (
                _get_books_with_keys(books_no_keys, sd_dicts, key_type)
                if key_type != KeyType.NONE
                else books_no_keys
            ),
            {k: tuple(v.values()) for k, v in sd_dicts.items()},
            tuple(sorted(chain.from_iterable([book.files for book in books_no_keys]))),
        )
