import json
from argparse import ArgumentParser
from .utils import freeze_file
from .subproject import Subproject
from os.path import join
from os import getcwd

def run():
    parser = ArgumentParser(description='Freeze a project dependencies')
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory", default=getcwd())
    optlist = parser.parse_args()

    root, modules = Subproject.create_dependency_tree(optlist.source_directory, update=False)
    freeze_conf = {}
    for name, mod in modules.items():
        freeze_conf[name] = mod.url_from_checkout()
    with open(join(root.directory, freeze_file), 'w') as f:
        json.dump(freeze_conf, f, indent=4, sort_keys = True)

if __name__ == "__main__":
    run()
