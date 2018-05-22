
from urllib.parse import urlparse
from argparse import ArgumentParser
from .subproject import generate_cmake_script
from os.path import abspath, basename
from os import getcwd

def run():
    parser = ArgumentParser(description='Download a project source tree with all dependencies')
    parser.add_argument("url", metavar="URL", nargs='?',
                        help="Specify the checkout URL directory")
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    parser.add_argument("-v", "--verbose", action='store_true',
                        help="Print dependency tree in JSON format")
    optlist = parser.parse_args()
    url = optlist.url
    source_dir = abspath(optlist.source_directory or (optlist.url and basename(urlparse(optlist.url).path)) or getcwd())
    generate_cmake_script(source_dir, url, print_tree=optlist.verbose)

if __name__ == "__main__":
    run()