from os.path import join, exists
from .utils import dependency_file, mkdir
from .checkout import Module

import json
import sys
from os import getcwd

def solve_dependencies(source_dir, build_dir, options={}):
    Module.subproject_dir = join(build_dir, 'quark', 'src')
    mkdir(Module.subproject_dir)
    modules = {}

    def load_conf(folder):
        filepath = join(folder, dependency_file)
        if exists(filepath):
            with open(join(folder, dependency_file), 'r') as f:
                return json.load(f)
        else:
            return None

    def add_module(parent, name, uri, options):
        newmodule = Module.create(name, uri, options)
        mod = modules.setdefault(name, newmodule)
        if mod is newmodule:
            mod.checkout()
        else:
            if not mod.same_checkout(newmodule):
                raise ValueError("Conflicting URLs for module '%s': '%s' and '%s'" % (name, mod.urlstring, newmodule.urlstring))
        for key, value in options.items():
            if mod.options.setdefault(key, value) != value:
                raise ValueError()
        parent.children.add(mod)

    root = Module()
    root.directory = source_dir
    stack = [root]
    while len(stack):
        current_module = stack.pop()
        conf = load_conf(current_module.directory)
        if conf:
            for name, depobject in conf.get('depends', {}).items():
                add_module(current_module, name, depobject['url'], depobject.get('options', {}))
            for option_key, optdepobject in conf.get('optdepends', {}).items():
                if ((option_key in options and options[option_key] == optdepobject['value']) or
                    (option_key in current_module.options and current_module.options[option_key] == optdepobject['value'])):
                    for name, depobject in optdepobject['depends'].items():
                        add_module(current_module, name, depobject['url'], depobject.get('options', {}))
            stack += list(current_module.children)
    return (root, modules)


if __name__ == '__main__':
    solve_dependencies((len(sys.argv) == 2 and sys.argv[1]) or getcwd(), '/tmp/subprojects')
