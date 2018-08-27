from contextlib import contextmanager
import sys
import os
import os.path as path
import subprocess
import argparse
import json
import logging
import errno
from urllib.request import urlopen

dependency_file = 'subprojects.quark'
freeze_file = 'freeze.quark'
logger = logging.getLogger(__name__)

def load_conf(folder):
    filepath = path.join(folder, dependency_file)
    if path.exists(filepath):
        jsonfile = path.join(folder, dependency_file)
        try:
            with open(jsonfile, 'r') as f:
                result = json.load(f)
                if isinstance(result, dict) and "catalog" in result:
                    # Fill-in with default options from catalog
                    cat = json.load(urlopen(result["catalog"]))
                    
                    def filldefault(depends):
                        for module, opts in depends.items():
                            name = opts.get("name", module.split("/")[-1])
                            if name in cat:
                                for opt, value in cat[name].items():
                                    if opt not in opts:
                                        opts[opt] = value

                    if "depends" in result:
                        filldefault(result["depends"])

                    if "optdepends" in result:
                        for option, deps in result["optdepends"].items():
                            for d in deps:
                                if "depends" in d:
                                    filldefault(d["depends"])
                return result
        except json.decoder.JSONDecodeError as err:
            logger.error("Error parsing '%s'" % jsonfile)
            raise err
    else:
        return None

def fork(*args, **kwargs):
    sys.stdout.write(' '.join(args[0]) + '\n')
    sys.stdout.flush()
    return subprocess.check_call(*args, **kwargs)

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
    except OSError as ex:
        if ex.errno != errno.EEXIST or not os.path.isdir(path):
            raise

def str2bool(v):
    if v.lower() in {'yes', 'true', 't', 'y', '1', 'on'}:
        return True
    elif v.lower() in {'no', 'false', 'f', 'n', '0', 'off'}:
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

@contextmanager
def DirectoryContext(newdir):
    prevdir = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(prevdir)
