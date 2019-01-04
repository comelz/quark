from argparse import ArgumentParser
from .subproject import generate_cmake_script, Subproject, url_from_directory
from .utils import parse_option
from os import getcwd

def run():
    parser = ArgumentParser(description='Update all dependencies in a project source tree')
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    parser.add_argument("-v", "--verbose", action='store_true',
                        help="Print dependency tree in JSON format")
    parser.add_argument("-o", "--options", action='append',
                    help="set option value (will be taken into account when downloading optional dependencies)")
    parser.add_argument("-d", "--deps-only", action='store_true', default=True,
            help="Update only dependencies, ignore the root project; this is " +
            "the default behavior, so this option now has no effect and is kept " +
            "only for compatibility with older scripts")
    optlist = parser.parse_args()
    source_dir = optlist.source_directory or getcwd()
    options = {}
    if optlist.options:
        for option in optlist.options:
            key, value = parse_option(option)
            options[key] = value

    if not optlist.deps_only:
        root_url = url_from_directory(source_dir, include_commit = False)
        root = Subproject.create("root", root_url, source_dir, {}, toplevel = True)
        root.update()
    generate_cmake_script(source_dir, print_tree=optlist.verbose, options=options)

if __name__ == "__main__":
    run()
