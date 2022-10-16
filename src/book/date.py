"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for BookDate.

"""
from dataclasses import dataclass
from datetime import datetime

_YEAR = "%Y"


@dataclass(frozen=True)
class BookDate:
    """Class for book date information."""

    _datetime: datetime

    def as_str(self, dt_fmt: str) -> str:
        """Get a formatted date string."""
        # There's a Python issue with inconsistent formatting for years < 1000 on some
        # platforms, see https://github.com/python/cpython/issues/57514.
        year_formatted = datetime.strftime(self._datetime, _YEAR).zfill(4)
        return year_formatted.join(
            [datetime.strftime(self._datetime, part) for part in dt_fmt.split(_YEAR)]
        )

    @classmethod
    def from_args(cls, dt_str: str, dt_fmt: str) -> "BookDate":
        """Get BookDate from args."""
        return cls(datetime.strptime(dt_str, dt_fmt))
