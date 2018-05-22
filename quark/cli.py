import sys
import json
from os import access, environ, pathsep, X_OK, listdir, getcwd
from os.path import isfile, split, join, abspath, basename, exists
from shutil import which
from subprocess import check_call, CalledProcessError
from quark.utils import mkdir, load_conf, freeze_file, dependency_file, walk_tree
from .subproject import Subproject
from argparse import ArgumentParser
from urllib.parse import urlparse

def main():
    try:
        if len(sys.argv) > 1 and which('quark-' + sys.argv[1]):
            check_call(['quark-' + sys.argv[1]] + sys.argv[2:])
        else:
            def is_exe(fpath):
                return isfile(fpath) and access(fpath, X_OK)
            exes = {}
            for path in environ["PATH"].split(pathsep):
                try:
                    for entry in listdir(path):
                        if not entry.startswith('quark-'):
                            continue
                        exe_file = join(path, entry)
                        if is_exe(exe_file) and not entry in exes:
                            exes[entry] = exe_file
                except FileNotFoundError:
                    pass
            print('\nAvailable commands:\n')
            for cmd in exes.keys():
                print('    ' + cmd.replace('quark-', ''))
    except CalledProcessError as cpe:
        sys.exit(cpe.returncode)
        pass

if __name__ == "__main__":
    main()