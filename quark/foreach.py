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
        version_control = "svn" if type(module) is SvnSubproject else "git"
        commit_sha = ""
        revision = ""

        if version_control == "svn":
            revision = module.rev

        if version_control == "git":
            commit_sha = module.ref

        module_relpath = os.path.relpath(
            module.directory, optlist.source_directory
        )
        module_name = module.name
        toplevel = os.path.abspath(optlist.source_directory)

        try:
            args = [
                os.path.abspath(x) if os.path.exists(x) else x
                for x in optlist.command.split()
            ]

            args.extend([
                "--toplevel", toplevel,
                "--path", module_relpath,
                "--name", module_name,
                "--version_control", version_control,
            ])

            if version_control == "git":
                args.extend(["--sha1", commit_sha])

            if version_control == "svn":
                args.extend(["--revision", revision])

            with change_dir(module.directory):
                subprocess.call(args)
        except Exception:
            raise
    pass


if __name__ == "__main__":
    run()
