"""
Copyright 2022, Jeremy Nation <jeremy@jeremynation.me>
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for BookKeyValue.

"""
from dataclasses import dataclass


@dataclass(frozen=True)
class BookKeyValue:
    """Represents a key-value pair."""

    key: str
    value: str
