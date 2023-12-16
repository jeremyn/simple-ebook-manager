"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Code for BookFile.

"""
from dataclasses import dataclass
from pathlib import Path

from src.util import DirVars, SimpleEbookManagerExit


@dataclass(order=True)
class BookFile:
    """Represents an actual file (EPUB, PDF etc) associated with a Book."""

    book_title_sort: str
    basename: str
    metadata_dir: Path
    dir_vars: DirVars
    input_dir_str: str
    hash: str
    fn: Path

    @classmethod
    def from_args(
        cls,
        book_title_sort: str,
        basename: str,
        metadata_dir: Path,
        dir_vars: DirVars,
        input_dir_str: str,
        hash_: str,
    ) -> "BookFile":
        """Get BookFile from args."""
        try:
            # process input_dir_str through Path to localize it for the current platform
            interpolated_dir = str(Path(input_dir_str)).format(
                **dict({dir_var.name: dir_var.value for dir_var in dir_vars})
            )
        except KeyError:
            dir_vars_str = (
                ", ".join([str(dir_var) for dir_var in dir_vars])
                if dir_vars
                else "<none provided>"
            )
            raise SimpleEbookManagerExit(
                f"ERROR: not enough dir_vars provided, metadata file directory: '{metadata_dir}', "
                f"file relative directory: '{input_dir_str}', dir_vars: '{dir_vars_str}'."
            ) from None

        return cls(
            book_title_sort,
            basename,
            metadata_dir,
            dir_vars,
            input_dir_str,
            hash_,
            temp_fn
            if (temp_fn := Path(interpolated_dir) / basename).is_absolute()
            else (metadata_dir / temp_fn).resolve(),
        )
