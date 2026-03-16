from os import environ, getcwd, pathsep
from os.path import exists, join
from subprocess import call
from sys import argv, exit

from quark.subproject import Subproject


def run():
    if len(argv) < 2:
        print("Not enough arguments")
        exit(1)

    paths = []
    _, modules = Subproject.create_dependency_tree(getcwd(), update=False)
    for module in modules.values():
        for path in module.quark_run_paths:
            module_path = join(module.directory, path)
            if not exists(module_path):
                continue
            paths.append(module_path)

    new_env = environ.copy()
    new_env["PATH"] = pathsep.join(paths) + pathsep + new_env["PATH"]

    exit(call(argv[1:], env=new_env))


if __name__ == "__main__":
    run()
