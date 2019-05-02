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
        "-q", "--quiet",
        help="Only print error messages"
    )
    parser.add_argument(
        "command",
        action="store",
        nargs="+",
        help="The command that will be run for every dependency"
    )

    optlist = parser.parse_args()
    optlist.source_directory = os.getcwd()

    root, modules = Subproject.create_dependency_tree(
        optlist.source_directory, update=False
    )

    for path, module in modules.items():
        version_control = "svn" if type(module) is SvnSubproject else "git"

        if version_control == "git":
            # Case for git
            commit_sha = module.ref
        else:
            # Case for SVN
            revision = module.rev

        module_relpath = os.path.relpath(
            module.directory, optlist.source_directory
        )
        module_name = module.name
        toplevel = os.path.abspath(optlist.source_directory)

        args = [
            os.path.abspath(x) if os.path.exists(x) else x
            for x in optlist.command[0].split()
        ]

        # name is the name of the submodule
        os.environ["name"] = str(module_name)

        # sm_path is the path of the submodule
        # as recorded in the immediate superproject
        os.environ["sm_path"] = str(module_relpath)

        # sha1 is the commit as recorded in the immediate superproject
        os.environ["sha1"] = str(commit_sha)

        # toplevel is the absolute path to the
        # top-level of the immediate superproject
        os.environ["toplevel"] = str(toplevel)

        with change_dir(module.directory):
            if optlist.quiet:
                subprocess.call(args, stdout=os.devnull)
            else:
                subprocess.call(args)



if __name__ == "__main__":
    run()
