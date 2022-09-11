"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for schemas.

"""
import inspect
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional, Sequence, Type

from .file import JSONType, get_csv_fn, get_schema_fn, read_json
from .misc import SimpleEbookManagerException, SimpleEbookManagerExit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SchemaItemBase:
    """Base class for schema items."""

    name: str


@dataclass(frozen=True)
class SchemaItemTypes:
    """Schema item types."""

    @dataclass(frozen=True)
    class Date(_SchemaItemBase):
        """Schema date."""

        input_format: str
        output_format: str

    @dataclass(frozen=True)
    class File(_SchemaItemBase):
        """Schema file."""

    @dataclass(frozen=True)
    class KeyValue(_SchemaItemBase):
        """Schema keyvalue."""

        key_label: str
        value_label: str

    @dataclass(frozen=True)
    class SortDisplay(_SchemaItemBase):
        """Schema sortdisplay."""

    @dataclass(frozen=True)
    class String(_SchemaItemBase):
        """Schema string."""

        inline: bool

    @dataclass(frozen=True)
    class Title(_SchemaItemBase):
        """Schema title."""


def _get_type_name(cls: Type[_SchemaItemBase]) -> str:
    """Get type name for given item type."""
    return cls.__name__.lower()


_SCHEMA_TYPE_MAPPING = {
    _get_type_name(m[1]): m[1]
    for m in inspect.getmembers(
        SchemaItemTypes,
        lambda cls: isinstance(cls, type) and issubclass(cls, _SchemaItemBase),
    )
}

# error if these are found, they can cause problems later
_NAMES_RESERVED = (get_csv_fn(None).stem,)
# at least one item of each of these types must be included
_TYPES_REQUIRED = (SchemaItemTypes.File, SchemaItemTypes.Title)
# error if any of these types appear more than once
_TYPES_NO_DUPLICATES = (SchemaItemTypes.File, SchemaItemTypes.Title)


class _InvalidDuplicatesExit(SimpleEbookManagerExit):
    pass


class _InvalidTypeExit(SimpleEbookManagerExit):
    pass


class _MissingRequiredTypeExit(SimpleEbookManagerExit):
    pass


class _ReservedNameExit(SimpleEbookManagerExit):
    pass


@dataclass(frozen=True)
class Schema:
    """Represents a parsed schema."""

    _schema_items: tuple[_SchemaItemBase, ...]

    def __iter__(self) -> Generator[_SchemaItemBase, None, None]:
        yield from self._schema_items

    @property
    def title_fieldname(self) -> str:
        """Get title item name from _schema_items."""
        for item in self:
            if isinstance(item, SchemaItemTypes.Title):
                return item.name
        raise SimpleEbookManagerException("no title found in schema")

    @classmethod
    def from_args(cls, schema_dict: JSONType) -> "Schema":
        """Get Schema from args."""
        schema_items: list[_SchemaItemBase] = []
        for name, type_raw in schema_dict.items():
            name = name.lower()
            if name in _NAMES_RESERVED:
                raise _ReservedNameExit(name)

            item_cls_kwargs = {"name": name}

            try:
                if isinstance(type_raw, str):
                    item_cls = _SCHEMA_TYPE_MAPPING[type_raw.lower()]
                else:
                    item_cls = _SCHEMA_TYPE_MAPPING[type_raw.pop("type").lower()]
                    item_cls_kwargs.update(type_raw)
            except Exception:
                raise _InvalidTypeExit(name) from None

            schema_items.append(item_cls(**item_cls_kwargs))

        for type_required in _TYPES_REQUIRED:
            type_found = False
            for item in schema_items:
                if isinstance(item, type_required):
                    type_found = True
                    break
            if not type_found:
                raise _MissingRequiredTypeExit(_get_type_name(type_required))

        for type_no_dup in _TYPES_NO_DUPLICATES:
            items_of_type = [
                item for item in schema_items if isinstance(item, type_no_dup)
            ]
            if len(items_of_type) > 1:
                raise _InvalidDuplicatesExit(
                    _get_type_name(type_no_dup),
                    [item.name for item in items_of_type],
                )

        return cls(tuple(schema_items))


def _read_schema_from_fn(fn: Path) -> Schema:
    """Read schema from fn."""
    try:
        return Schema.from_args(read_json(fn))
    except _InvalidDuplicatesExit as exc:
        raise SimpleEbookManagerExit(
            f"ERROR: duplicate items with type '{exc.args[0]}' found in '{fn}', item names: "
            f"{', '.join(exc.args[1])}."
        ) from None
    except _InvalidTypeExit as exc:
        raise SimpleEbookManagerExit(
            f"ERROR: problem processing type for item name '{exc.args[0]}' found in '{fn}'."
        ) from None
    except _MissingRequiredTypeExit as exc:
        raise SimpleEbookManagerExit(
            f"ERROR: item with required type '{exc.args[0]}' not found in '{fn}'."
        ) from None
    except _ReservedNameExit as exc:
        raise SimpleEbookManagerExit(
            f"ERROR: reserved name '{exc.args[0]}' found in '{fn}' (reserved name(s) are: "
            f"{', '.join(_NAMES_RESERVED)})."
        ) from None


def _read_schema_from_dirs(dirs: Sequence[Path]) -> tuple[Sequence[Path], Schema]:
    """Read schema from dirs."""
    schemas = {}
    for dir_ in dirs:
        fn = get_schema_fn(dir_)
        if not fn.is_file():
            continue
        schemas[fn] = _read_schema_from_fn(fn)

    if not schemas:
        raise SimpleEbookManagerExit(
            "ERROR: schema filename not provided and no "
            f"'{get_schema_fn(Path('.')).name}' found in dirs."
        )

    if len(set(schemas.values())) != 1:
        raise SimpleEbookManagerExit(
            "ERROR: schema filename not provided and at least two dir schemas conflict."
        )

    return list(schemas.keys()), list(schemas.values())[0]


def _log(fns: Path | Sequence[Path]) -> None:
    """Log schema usage."""
    if isinstance(fns, Path) or len(fns) == 1:
        logger.info("Using schema from '%s'.", fns if isinstance(fns, Path) else fns[0])
    else:
        logger.info(
            "Using matching schemas from: '%s'.", "', '".join([str(fn) for fn in fns])
        )


def read_schema(
    *, fn: Optional[Path] = None, dirs: Optional[Sequence[Path]] = None
) -> Schema:
    """Read schema from fn or dirs."""
    if fn is not None:
        schema = _read_schema_from_fn(fn)
        _log(fn)
        return schema

    if dirs is not None:
        schema_fns, schema = _read_schema_from_dirs(dirs)
        _log(schema_fns)
        return schema

    raise SimpleEbookManagerException("at least one input arg must be set")
