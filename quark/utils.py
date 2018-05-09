import sys
import os
import os.path as path
import subprocess
import argparse
import hashlib
import json

cache_file = os.path.join('quark', 'quark_cache.json')
dependency_file = 'subprojects.quark'
freeze_file = 'freeze.quark'


def load_conf(folder):
    filepath = path.join(folder, dependency_file)
    if path.exists(filepath):
        with open(path.join(folder, dependency_file), 'r') as f:
            return json.load(f)
    else:
        return None


def walk_tree(root, callback):
    class StackElement:
        def __init__(self, node):
            self.node = node
            self.index = 0
            self.children = list(node.children)

    stack = [StackElement(root)]
    while len(stack) > 0:
        stack_element = stack[-1]
        if stack_element.index == len(stack_element.children):
            if callback.__code__.co_argcount == 1:
                callback(stack_element.node)
            if callback.__code__.co_argcount == 2:
                callback(stack_element.node, len(stack))
            stack.pop()
        else:
            child = stack_element.children[stack_element.index]
            stack.append(StackElement(child))
            stack_element.index += 1


def update_dict(original, updated):
    for key, value in updated.items():
        fixed_key = key.replace('-', '_')
        if fixed_key in original and isinstance(value, dict):
            update_dict(original[fixed_key], value)
        elif not fixed_key in original:
            original[fixed_key] = value
        elif fixed_key in original and value:
            original[fixed_key] = value


def fork(*args, **kwargs):
    sys.stdout.write(' '.join(args[0]) + '\n')
    return subprocess.check_call(*args, **kwargs)


def dump_option(key, value):
    if isinstance(value, bool):
        return '-D%s=%s' % (key, 'ON' if value else 'OFF')
    else:
        return '-D%s=%s' % (key, value)


def parse_option(s):
    eq = s.find('=')
    if eq < 0:
        raise ValueError('Unable to parse option: "%s"' % s)
    colon = s.find(':')
    if colon < 0:
        colon = eq
        key, value = s[:colon], s[eq + 1:]
        try:
            value = str2bool(value)
        except argparse.ArgumentTypeError:
            pass
    else:
        key = s[:colon]
        ty = s[colon + 1:eq].lower()
        if ty == 'BOOL':
            value = str2bool(s[eq + 1])
        else:
            value = s[eq + 1]
    return key, value


def mkdir(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if not os.path.exists(path):
            raise e


def write_if_different(filepath, content, bufsize=256 * 256):
    newdigest = hashlib.md5(content.encode()).digest()
    md5 = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while True:
                buffer = f.read(bufsize)
                md5.update(buffer)
                if len(buffer) < bufsize:
                    break
    except FileNotFoundError:
        pass
    if md5.digest() != newdigest:
        open(filepath, 'w').write(content)


def mkpushd(path): mkdir(path) and pushd(path)


def mkcd(path): mkdir(path) and os.chdir(path)


def str2bool(v):
    if v.lower() in {'yes', 'true', 't', 'y', '1', 'on'}:
        return True
    elif v.lower() in {'no', 'false', 'f', 'n', '0', 'off'}:
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)


def strip(filepath, ts_filepath=None):
    if not ts_filepath:
        ts_filepath = filepath + '.strip_timestamp'
    touch(ts_filepath)
    subprocess.check_output(['strip', '-s', filepath])


def upx(filepath, ts_filepath=None):
    if not ts_filepath:
        ts_filepath = filepath + '.upx_timestamp'
    touch(ts_filepath)
    subprocess.check_output(['upx', '--best', filepath])


def _init():
    dir_stack = []

    def pushd(*args):
        dir_stack.append(os.getcwd())
        ndir = os.path.realpath(os.path.join(*args))
        os.chdir(ndir)

    def popd():
        odir = dir_stack.pop()
        os.chdir(odir)

    return pushd, popd


pushd, popd = _init()


class DirectoryContext:
    def __init__(self, dirpath, create=False):
        self.dirpath = dirpath
        self.create = create

    def __enter__(self):
        mkpushd(self.dirpath) if self.create else pushd(self.dirpath)
        return self.dirpath

    def __exit__(self, *args):
        popd()


class SubprocessContext:
    def __init__(self, cmd, **kwargs):
        if 'check' in kwargs:
            self.check = kwargs['check']
            del kwargs['check']
        else:
            self.check = False
        self.pipe = subprocess.Popen(cmd, **kwargs)
        self.cmd = cmd

    def __enter__(self):
        return self.pipe

    def __exit__(self, *args):
        if self.check:
            self.pipe.communicate()
            if self.pipe.returncode != 0:
                raise subprocess.CalledProcessError(self.pipe.returncode, self.cmd)


def classproperty(func):
    if not isinstance(func, (classmethod, staticmethod)):
        func = classmethod(func)

    class ClassPropertyDescriptor(object):

        def __init__(self, fget, fset=None):
            self.fget = fget
            self.fset = fset

        def __get__(self, obj, klass=None):
            if klass is None:
                klass = type(obj)
            return self.fget.__get__(obj, klass)()

        def __set__(self, obj, value):
            if not self.fset:
                raise AttributeError("can't set attribute")
            type_ = type(obj)
            return self.fset.__get__(obj, type_)(value)

        def setter(self, func):
            if not isinstance(func, (classmethod, staticmethod)):
                func = classmethod(func)
            self.fset = func
            return self

    return ClassPropertyDescriptor(func)
