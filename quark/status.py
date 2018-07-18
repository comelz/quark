import json
from argparse import ArgumentParser
from .utils import freeze_file
from .subproject import Subproject
from os.path import join
from os import getcwd

def run():
    parser = ArgumentParser(description='Check a project status')
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory", default=getcwd())
    optlist = parser.parse_args()

    root, modules = Subproject.create_dependency_tree(optlist.source_directory, update=False)
    for mod in ([root] + list(modules.values())):
        print("=== Status of %s" % mod.directory)
        mod.status()
        print()

if __name__ == "__main__":
    run()
