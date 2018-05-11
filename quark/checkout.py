import json
import os
from argparse import ArgumentParser
from os.path import exists, join, basename
from urllib.parse import urlparse

from quark.utils import mkdir, load_conf, freeze_file, dependency_file, walk_tree
from .subproject import Subproject


def checkout():
    parser = ArgumentParser(description='Download a project source tree with all dependencies')
    parser.add_argument("url", metavar="URL", nargs='?',
                        help="Specify the checkout URL directory")
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    parser.add_argument("-v", "--verbose", action='store_true',
                        help="Print dependency tree in JSON format")
    optlist = parser.parse_args()
    url = optlist.url
    source_dir = optlist.source_directory or (optlist.url and basename(urlparse(optlist.url).path)) or os.getcwd()
    resolve_dependencies(source_dir, url, print_tree=optlist.verbose)

def update():
    parser = ArgumentParser(description='Update all dependencies in a project source tree')
    parser.add_argument("source_directory", metavar="SOURCE_DIR", nargs='?',
                        help="Specify the source directory")
    parser.add_argument("-v", "--verbose", action='store_true',
                        help="Print dependency tree in JSON format")
    optlist = parser.parse_args()
    source_dir = optlist.source_directory or os.getcwd()
    resolve_dependencies(source_dir, print_tree=optlist.verbose)

def resolve_dependencies(source_dir, url=None, options=None, print_tree=False):
    subproject_dir = join(source_dir, 'lib')
    if url:
        root = Subproject.create(basename(source_dir), url, source_dir)
        root.checkout()
    else:
        root = Subproject(directory=os.getcwd(), options=options or {})
    stack = [root]
    modules = {}

    def get_option(key):
        try:
            return root.options[key]
        except KeyError as e:
            err = e
        for module in modules.values():
            try:
                return module.options[key]
            except KeyError as e:
                err = e
        raise err

    def add_module(parent, name, uri, options, **kwargs):
        newmodule = Subproject.create(name, uri, join(subproject_dir, name), options, **kwargs)
        mod = modules.setdefault(name, newmodule)
        if mod is newmodule:
            mod.parents.add(parent)
            mod.checkout()
            stack.append(mod)
        else:
            if not newmodule.same_checkout(mod):
                children = [join(parent.directory, dependency_file) for parent in mod.parents]
                parent = join(parent.directory, dependency_file)
                raise ValueError(
                    "Conflicting URLs for module '%s': '%s' required by %s and '%s' required by '%s'" %
                    (name,
                     mod.urlstring, children,
                     newmodule.urlstring, parent))

            else:
                for key, value in options.items():
                    mod.options.setdefault(key, value)
                    if mod.options[key] != value:
                        raise ValueError(
                            "Conflicting values option '%s' of module '%s'" % (key, mod.name)
                        )
        parent.children.add(mod)

    freeze_conf = join(root.directory, freeze_file)
    if exists(freeze_conf):
        with open(freeze_conf, 'r') as f:
            freeze_dict = json.load(f)
    else:
        freeze_dict = {}
    mkdir(subproject_dir)
    while len(stack):
        current_module = stack.pop()
        conf = load_conf(current_module.directory)
        if conf:
            for name, depobject in conf.get('depends', {}).items():
                add_module(current_module, name,
                    freeze_dict.get(name, depobject.get('url', None)), depobject.get('options', {}),
                    exclude_from_cmake=depobject.get('exclude_from_cmake', False))
            for key, optobjects in conf.get('optdepends', {}).items():
                if isinstance(optobjects, dict):
                    optobjects = [optobjects]
                for optobject in optobjects:
                    try:
                        value = get_option(key)
                    except KeyError:
                        continue
                    if value == optobject['value']:
                        for name, depobject in optobject['depends'].items():
                            add_module(current_module, name,
                                freeze_dict.get(name, depobject.get('url', None)), depobject.get('options', {}))
    if print_tree:
        print(json.dumps(root.toJSON(), indent=4))

    with open(join(subproject_dir, 'CMakeLists.txt'), 'w') as cmake_lists_txt:
        processed = {None}
        def cb(module):
            if module.name in processed or module.exclude_from_cmake or not exists(join(module.directory, "CMakeLists.txt")):
                return
            for key, value in module.options.items():
                if value is None:
                    cmake_lists_txt.write('unset(%s CACHE)\n' % (key))
                    continue
                elif isinstance(value, bool):
                    kind = "BOOL"
                    value = 'ON' if value else 'OFF'
                else:
                    kind = "STRING"
                cmake_lists_txt.write('set(%s %s CACHE INTERNAL "" FORCE)\n' % (key, value))
            cmake_lists_txt.write('add_subdirectory(%s)\n' % (module.directory))
            processed.add(module.name)

        walk_tree(root, cb)

if __name__ == "__main__":
    checkout()
