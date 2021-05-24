
from urllib.parse import urlparse
from argparse import ArgumentParser
from .subproject import init_subprojects_dir
from os.path import abspath, basename
from .utils import parse_option
from os import getcwd

def run():
    parser = ArgumentParser(description='Download a project source tree with all dependencies')
    parser.add_argument("url", metavar="URL", nargs='?',
                        help="Specify the checkout URL directory")
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    parser.add_argument("-v", "--verbose", action='store_true',
                        help="Print dependency tree in JSON format")
    parser.add_argument("-o", "--options", action='append',
                    help="set option value (will be taken into account when downloading optional dependencies)")
    optlist = parser.parse_args()
    url = optlist.url
    options = {}
    if optlist.options:
        for option in optlist.options:
            key, value = parse_option(option)
            options[key] = value
    source_dir = abspath(optlist.source_directory or (optlist.url and basename(urlparse(optlist.url).path)) or getcwd())
    init_subprojects_dir(source_dir, url, print_tree=optlist.verbose, options=options)

if __name__ == "__main__":
    run()
