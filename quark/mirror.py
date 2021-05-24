from argparse import ArgumentParser
from .subproject import Subproject
from .utils import parse_option
import os

def run():
    parser = ArgumentParser(description='Update all dependencies in a project source tree')
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    parser.add_argument('destination', metavar='destination', type=str,
                        help='destination directory')
    optlist = parser.parse_args()
    source_dir = optlist.source_directory or os.getcwd()
    dest_dir = optlist.destination

    root = Subproject.create("root", None, source_dir, {}, toplevel = True)
    root.mirror(dest_dir)

    root, modules = Subproject.create_dependency_tree(source_dir, update=False)
    for mod in (list(modules.values())):
        relpath = os.path.relpath(mod.directory, source_dir)
        dest_subdir = os.path.join(dest_dir, relpath)
        mod.mirror(dest_subdir)

if __name__ == "__main__":
    run()
