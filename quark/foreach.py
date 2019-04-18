# -*- coding: utf-8 *--

import os
import subprocess
import contextlib

from argparse import ArgumentParser
from .subproject import Subproject
from .subproject import SvnSubproject


@contextlib.contextmanager
def change_dir(path):
    _old_path = os.getcwd()

    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(_old_path)


def run():
    parser = ArgumentParser(
        description="Iter a command through all the dependencies"
    )

    parser.add_argument(
        "--source_directory", "--src",
        metavar="SOURCE_DIR", nargs='?',
        help="Specify the source directory", default=os.getcwd()
    )
    parser.add_argument(
        "command",
        action="store",
        nargs='?',
        help="The command that will be run for every dependency"
    )

    optlist = parser.parse_args()

    root, modules = Subproject.create_dependency_tree(
        optlist.source_directory, update=False
    )

    for path, module in modules.items():
        if type(module) is SvnSubproject:
            continue

        commit_sha = module.ref
        module_relpath = os.path.relpath(
            module.directory, optlist.source_directory
        )
        module_name = module.name
        toplevel = os.path.abspath(optlist.source_directory)

        # os.path["name"] = module_name
        # os.path["path"] = module_relpath
        # os.path["sha1"] = commit_sha
        # os.path["toplevel"] = toplevel

        try:
            args = optlist.command.split()
            args.extend([
                "--name", module_name,
                "--path", module_relpath,
                "--sha1", commit_sha,
                "--toplevel", toplevel
            ])
            with change_dir(module.directory):
                subprocess.check_call(args, shell=True)
        except Exception:
            raise
    pass


if __name__ == "__main__":
    run()
