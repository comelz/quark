import json
import os
from argparse import ArgumentParser
from os.path import exists, join, basename
from urllib.parse import urlparse

from quark.utils import mkdir, freeze_file, load_conf
from .subproject import Subproject

def freeze():
    parser = ArgumentParser(description='Freeze a project dependencies')
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    optlist = parser.parse_args()

    source_dir = optlist.source_directory or None

    modules = {}
    subproject_dir = join(source_dir or os.getcwd(), 'lib')

    def add_module(parent, name, uri):
        newmodule = Subproject.create(name, uri, join(subproject_dir, name))
        mod = modules.setdefault(name, newmodule)
        if not mod is newmodule:
            if not mod.same_checkout(newmodule):
                raise ValueError(
                    "Conflicting URLs for module '%s': '%s' and '%s'" % (name, mod.urlstring, newmodule.urlstring))
        parent.children.add(mod)

    root = Subproject(directory=os.getcwd())
    stack = [root]
    mkdir(subproject_dir)
    while len(stack):
        current_module = stack.pop()
        conf = load_conf(current_module.directory)
        if conf:
            for name, depobject in conf.items():
                add_module(current_module, name, depobject['url'])
            stack += list(current_module.children)

    freeze_conf = {}
    for name, mod in modules.items():
        freeze_conf[name] = mod.url_from_checkout()
    with open(join(root.directory, freeze_file), 'w') as f:
        json.dump(freeze_conf, f, indent=4)
