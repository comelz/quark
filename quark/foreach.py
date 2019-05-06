# -*- coding: utf-8 *--

import os
import subprocess
from argparse import ArgumentParser

from quark.utils import DirectoryContext

from .subproject import Subproject


def run():
    parser = ArgumentParser(
        description="""
        Evaluates an arbitrary shell command in each submodule, skipping all
        the svn's submodules.
        The command has access to the variables $name, $sm_path, $displaypath,
        $sha1, $toplevel, $rev, $version_control:
        $name is the name of the submodule;
        $sm_path is the path of the submodule relative to the superproject;
        $displaypath is the path of the submodule relative to the root
        directory;
        $version_control is the version control used by the subproject
        (git/svn);
        $sha1 is the commit of the subproject ( empty string if it is a
        svn repository );
        $rev is the revision of the subproject ( empty string if it is a
        git repository );
        $toplevel is the absolute path to the top-level of the
        immediate superproject.
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

    root, modules = Subproject.create_dependency_tree(
        os.getcwd(), update=False
    )

    for path, module in modules.items():
        module_relpath = os.path.relpath(module.directory, os.getcwd())
        module_displaypath = os.path.relpath(module.directory, os.getcwd())
        module_name = module.name
        toplevel = os.path.abspath(os.getcwd())
        version_control = module.get_version_control()

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

        # toplevel is the absolute path to the
        # top-level of the immediate superproject
        os.environ["toplevel"] = str(toplevel)

        # version_control is the version control used for the subproject
        os.environ["version_control"] = version_control

        if version_control == "git":
            # Case for git
            # sha1 is the commit of the subproject ( empty string
            # if it is a svn repository )
            os.environ["sha1"] = str(module.ref)
        else:
            # Case for SVN
            # rev is the revision of the subproject ( empty string if
            # it is a git repository )
            os.environ["rev"] = module.rev

        with DirectoryContext(module.directory):
            output = subprocess.check_output(cmd, shell=True)

            if not optlist.quiet:
                print(output.decode("utf-8"))

        try:
            del os.environ["sha1"]
        except KeyError:
            del os.environ["rev"]


if __name__ == "__main__":
    run()
