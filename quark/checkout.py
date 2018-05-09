import json
import os
from argparse import ArgumentParser
from os.path import exists, join, basename
from urllib.parse import urlparse

from quark.utils import mkdir, load_conf, freeze_file, dependency_file
from .subproject import Subproject


def checkout():
    parser = ArgumentParser(description='Download a project source tree with all dependencies')
    parser.add_argument("url", metavar="URL", nargs='?',
                        help="Specify the checkout URL directory")
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    optlist = parser.parse_args()

    url = optlist.url
    source_dir = optlist.source_directory or (optlist.url and basename(urlparse(optlist.url).path)) or None

    modules = {}
    subproject_dir = join(source_dir or os.getcwd(), 'lib')

    def add_module(parent, name, uri):
        newmodule = Subproject.create(name, uri, join(subproject_dir, name))
        mod = modules.setdefault(name, newmodule)
        res = None
        if mod is newmodule:
            mod.parents.add(parent)
            mod.checkout()
            res = mod
        else:
            if not mod.same_checkout(newmodule):
                raise ValueError(
                    "Conflicting URLs for module '%s': '%s' required by %s and '%s' required by '%s'" % (name,
                    mod.urlstring, [join(parent.directory, dependency_file) for parent in mod.parents],
                    newmodule.urlstring, join(parent.directory, dependency_file)))
        parent.children.add(mod)
        return res

    if source_dir:
        root = Subproject.create(basename(source_dir), url, source_dir)
        root.checkout()
    else:
        root = Subproject(directory=os.getcwd())

    freeze_conf = join(root.directory, freeze_file)
    if exists(freeze_conf):
        with open(freeze_conf, 'r') as f:
            freeze_dict = json.load(f)
    else:
        freeze_dict = {}
    stack = [root]
    mkdir(subproject_dir)
    while len(stack):
        current_module = stack.pop()
        conf = load_conf(current_module.directory)
        if conf:
            for name, depobject in conf.items():
                mod = add_module(current_module, name, freeze_dict.get(name, depobject['url']))
                if mod:
                    stack.append(mod)


if __name__ == "__main__":
    checkout()
