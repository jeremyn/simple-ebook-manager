"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Miscellaneous code.

"""
import enum
import hashlib
import itertools
import logging
from dataclasses import dataclass
from multiprocessing.pool import Pool
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from hashlib import _Hash
    from unittest._log import _LoggingWatcher

LOG_LEVEL = logging.INFO

#### DirVar


@dataclass(frozen=True, order=True)
class DirVar:
    """Class for holding a dir var."""

    name: str
    value: str

    def __str__(self) -> str:
        return "=".join([self.name, self.value])


DirVars = Sequence[DirVar]

#### Exceptions


class SimpleEbookManagerException(Exception):
    """Exception for programming error."""


class SimpleEbookManagerExit(SystemExit):
    """System exit for user input problems."""


#### Hashes


class Algorithm(enum.Enum):
    """Represents the user-requested hashing algorithm."""

    DEFAULT = enum.auto()
    MD5 = enum.auto()
    SHA256 = enum.auto()


def get_algo(algo_str: Optional[str], f_hash: str) -> Optional[Algorithm]:
    """Get Algorithm or None."""
    if algo_str is None:
        return None

    if (algo := Algorithm[algo_str.upper()]) != Algorithm.DEFAULT:
        return algo

    return Algorithm[f_hash.split(":")[0].upper()]


def _get_file_hash(input_fn: Path, algo: Algorithm) -> str:
    """Get the hash of input_fn with the specified algorithm."""
    algo_name = algo.name.lower()
    hash_obj: "_Hash" = getattr(hashlib, algo_name)()
    with input_fn.open(mode="rb") as file:
        while data := file.read(2**16):
            if not data:
                break
            hash_obj.update(data)

    return ":".join([algo_name, hash_obj.hexdigest()])


def get_file_hashes(inputs: Sequence[Path], algo: Algorithm) -> dict[Path, str]:
    """Get the hashes of inputs with the specified algorithm."""
    with Pool() as pool:
        hashes = pool.starmap(_get_file_hash, zip(inputs, itertools.repeat(algo)))
    return dict(zip(inputs, hashes, strict=True))


#### Other


def configure_logging() -> None:
    """Configure logging."""
    logging.basicConfig(format="%(message)s", level=LOG_LEVEL)


def get_log_records(cm: "_LoggingWatcher") -> Sequence[str]:
    """Get log messages."""
    return tuple(r.getMessage() for r in cm.records)
