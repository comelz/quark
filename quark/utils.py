from contextlib import contextmanager
import sys
import os
import os.path as path
import subprocess
import argparse
import json
import logging
import errno
import copy

dependency_file = 'subprojects.quark'
freeze_file = 'freeze.quark'
logger = logging.getLogger(__name__)
catalog_cache = {}
catalog_urls_overrides = {}

def workaround_url_read(url):
    """
    Tries to perform an urlopen(url).read(), with workarounds for broken
    certificate stores.

    On many Python installations, urllib has problems using the system
    certificate stores; this seems to be particularly true on macOS, it is so
    in a twisted way on Win32 and can be a problem on some Linux distros (where
    in general the very definition of "system certificates store" is somewhat
    confused). For the horrible details, see:

    https://stackoverflow.com/a/42107877/214671
    https://stackoverflow.com/q/52074590/214671

    A possibility could be to require the certifi package and use the
    certificates it provides (as requests does), but it's yet another thing to
    install and, most importantly, to keep updated (those pesky certificates do
    love to expire).

    On the other hand, on pretty much every macOS (and Linux) machine there's
    some system-provided cURL command-line tool that should work fine with the
    system certificate store; so, if urllib fails due to SSL errors, we try
    that route as well.
    """
    from urllib.request import urlopen
    from urllib.error import URLError
    try:
        return urlopen(url).read()
    except URLError as ex:
        import ssl
        if len(ex.args) and isinstance(ex.args[0], ssl.SSLError):
            logger.warn("SSL error reading catalog file %s, trying with command-line curl..." % url)
            def curl_url_read(url):
                return log_check_output(["curl", "-s", url])

            try:
                # Try with command-line cURL
                return curl_url_read(url)
            except:
                # Re-raise original exception - maybe SSL _is_ broken after all
                raise ex
            # It worked out fine, don't waste time with urllib in the future
            workaround_url_read = curl_url_read
        raise

def load_conf(folder):
    filepath = path.join(folder, dependency_file)
    if path.exists(filepath):
        jsonfile = path.join(folder, dependency_file)
        try:
            with open(jsonfile, 'r') as f:
                result = json.load(f)
                if isinstance(result, dict) and "catalog" in result:
                    # Fill-in with default options from catalog
                    catalog_url = result["catalog"]

                    # None is used as placeholder for the first fetched catalog
                    if None in catalog_urls_overrides:
                        catalog_urls_overrides[catalog_url] = catalog_urls_overrides[None]
                        del catalog_urls_overrides[None]

                    # If we have an override, use the overridden URL
                    if catalog_url in catalog_urls_overrides:
                        catalog_url = catalog_urls_overrides[catalog_url]

                    # The catalog is often the same for all dependencies, don't
                    # hammer the server *and* make sure we have a coherent view
                    if catalog_url not in catalog_cache:
                        catalog_cache[catalog_url] = json.loads(workaround_url_read(catalog_url).decode('utf-8'))
                    cat = catalog_cache[catalog_url]

                    def filldefault(depends):
                        for module, opts in depends.items():
                            name = opts.get("name", module.split("/")[-1])
                            if name in cat:
                                for opt, value in cat[name].items():
                                    if opt not in opts:
                                        opts[opt] = copy.deepcopy(value)

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

def print_cmd(cmd, comment = "", stream = sys.stdout):
    if comment:
        comment = " (" + comment + ")"
    yellow = green = reset = blue = ""
    if os.isatty(stream.fileno()):
        yellow = "\x1b[33m"
        green = "\x1b[32m"
        reset = "\x1b[30m\x1b(B\x1b[m"
        blue  = "\x1b[34m"
    stream.write(
        yellow + "quark: " +
        green + os.getcwd() + reset + '$ ' +
        ' '.join(cmd) +
        blue + comment +
        reset + "\n")
    stream.flush()

def fork(*args, **kwargs):
    print_cmd(args[0])
    return subprocess.check_call(*args, **kwargs)

def log_check_output(*args, **kwargs):
    print_cmd(args[0], "captured")
    return subprocess.check_output(*args, **kwargs)

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
