"""
Copyright Jeremy Nation <jeremy@jeremynation.me>.
Licensed under the GNU Affero General Public License (AGPL) v3.

Run user-specified custom code.

"""
import importlib.util
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Optional, Sequence, cast

from src.all_metadata import get_all_book_dirs
from src.command import Args, CmdNames, Command
from src.util import (
    SimpleEbookManagerException,
    read_json,
    read_text,
    write_json,
    write_text,
)

IOFuncs = SimpleNamespace(
    read_json=read_json,
    read_text=read_text,
    write_json=write_json,
    write_text=write_text,
)

_ProcessFuncType = Callable[[Sequence[Path], list[str], SimpleNamespace], None]


def get_process_func(user_module: str) -> _ProcessFuncType:
    """Import user_module.

    See https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly.

    """
    module_fn = Path(user_module)
    module_name = module_fn.stem
    spec = importlib.util.spec_from_file_location(module_name, module_fn)
    if (spec is None) or (spec.loader is None):
        raise SimpleEbookManagerException("unexpected problem importing user code")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return cast(_ProcessFuncType, module.process)


def main(known_args: Namespace, extra_args: Optional[list[str]] = None) -> None:
    """Main code for executing command."""
    if extra_args is None:
        # extra_args is Optional because it shares a common signature
        raise SimpleEbookManagerException("extra_args should never be None")
    process = get_process_func(known_args.user_module)
    process(get_all_book_dirs(known_args.library_dirs), extra_args, IOFuncs)


def get_cmd() -> Command:
    """Get Command."""
    _desc = f"""
    Run user code over the given library directories. The Python file passed to the 
    `{Args.USER_MODULE.opt}` option should have a `process` function with a specific signature. See 
    the README for more information.
    """
    return Command(
        args=(Args.LIBRARY_DIRS, Args.USER_MODULE),
        cmd_name=CmdNames.CUSTOM,
        has_extra_args=True,
        main=main,
        subparser_kwargs={"description": _desc, "help": "custom command for user code"},
    )
