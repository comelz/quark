# -*- coding: utf-8 *--

import os
import subprocess
import contextlib
from argparse import ArgumentParser



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
        description="""
        Evaluates an arbitrary shell command in each submodule, skipping all
        the svn's submodules.
        The command has access to the variables $name, $sm_path, $displaypath,
        $sha1 and $toplevel:
        $name is the name of the submodule;
        $sm_path is the path of the submodule relative to the superproject;
        $displaypath is the path of the submodule relative to the root directory;
        $sha1 is the commit as recorded in the immediate superproject;
        $toplevel is the absolute path to the top-level of the immediate superproject.
        """
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
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
        module_relpath = os.path.relpath(
            module.directory, optlist.source_directory
        )
        module_displaypath = os.path.relpath(
            module.directory, os.getcwd()
        )
        module_name = module.name
        toplevel = os.path.abspath(optlist.source_directory)

        if module.get_version_control() == "git":
            # Case for git
            commit_sha = module.ref
        else:
            # Case for SVN
            if not optlist.quiet:
                print(
                    "WARNING: {} at {} has been skipped because it's a "
                    "SVN repository\n".format(
                        module_name,
                        module_displaypath
                    ))
            continue

        cmd = " ".join([
            os.path.abspath(x) if os.path.exists(x) else x
            for x in optlist.command[0].split()
        ])

        # name is the name of the submodule
        os.environ["name"] = str(module_name)

        # sm_path is the path of the submodule
        # as recorded in the immediate superproject
        os.environ["sm_path"] = str(module_relpath)

        # displaypath contains the relative path from
        # the current working directory to the submodules root directory
        os.environ["displaypath"] = str(module_displaypath)

        # sha1 is the commit as recorded in the immediate superproject
        os.environ["sha1"] = str(commit_sha)

        # toplevel is the absolute path to the
        # top-level of the immediate superproject
        os.environ["toplevel"] = str(toplevel)

        with change_dir(module.directory):
            output = subprocess.check_output(cmd, shell=True)

            if not optlist.quiet:
                print(output.decode("utf-8"))


if __name__ == "__main__":
    run()
