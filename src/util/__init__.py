"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Public exports from util package.

"""
from .file import (
    Newline,
    cmp,
    get_csv_fn,
    get_db_fn,
    get_metadata_fn,
    get_newline,
    get_schema_fn,
    get_string_fn,
    read_json,
    read_metadata,
    read_text,
    write_csv,
    write_json,
    write_schema,
    write_text,
)
from .misc import (
    LOG_LEVEL,
    Algorithm,
    DirVar,
    DirVars,
    SimpleEbookManagerException,
    SimpleEbookManagerExit,
    configure_logging,
    get_file_hashes,
    get_log_records,
)
from .schema import Schema, SchemaItemTypes, read_schema

__all__ = [
    # file
    "Newline",
    "cmp",
    "get_csv_fn",
    "get_db_fn",
    "get_metadata_fn",
    "get_newline",
    "get_schema_fn",
    "get_string_fn",
    "read_json",
    "read_metadata",
    "read_text",
    "write_csv",
    "write_json",
    "write_schema",
    "write_text",
    # misc
    "Algorithm",
    "DirVar",
    "DirVars",
    "LOG_LEVEL",
    "SimpleEbookManagerException",
    "SimpleEbookManagerExit",
    "configure_logging",
    "get_file_hashes",
    "get_log_records",
    # schema
    "Schema",
    "SchemaItemTypes",
    "read_schema",
]
