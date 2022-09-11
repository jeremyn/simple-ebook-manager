"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for SortDisplay.

"""
from dataclasses import dataclass
from typing import Optional

from src.util import SimpleEbookManagerException


@dataclass(frozen=True, order=True)
class SortDisplay:
    """Represents an item to be cross-referenced between Books."""

    sort: str
    display: str
    _key: Optional[str] = None

    @property
    def key(self) -> str:
        """Error if a None key is requested, else return _key."""
        if self._key is None:
            raise SimpleEbookManagerException(f"key for 'sort={self.sort}' is None")
        return self._key
