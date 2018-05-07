import fcntl
import logging
import os
from hashlib import md5
from os import listdir
from os.path import exists, join, expanduser
from shutil import rmtree
from subprocess import check_output, call, PIPE
from time import sleep
from urllib.parse import urlparse

from lxml import etree

from quark.utils import DirectoryContext, mkdir, fork, classproperty, SubprocessContext

logger = logging.getLogger(__name__)


class FileLock:
    def __init__(self, filepath):
        self._filepath = filepath

    def __enter__(self):
        import errno
        self._fd = os.open(self._filepath, os.O_RDONLY)
        while True:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as e:
                if e.errno != errno.EAGAIN:
                    raise
                else:
                    sleep(0.3)

    def __exit__(self, *args):
        fcntl.flock(self._fd, fcntl.LOCK_UN)
        os.close(self._fd)


def repo_cleanup():
    with FileLock(checkout_dir):
        for entry in listdir(checkout_dir):
            sandbox_dir = join(checkout_dir, entry)
            refcount_file = join(sandbox_dir, '.czmake_refcount')
            existing_build_dirs = []
            rewrite = False
            with open(refcount_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if exists(line):
                        existing_build_dirs.append(line)
                    else:
                        rewrite = True
            if rewrite:
                if len(existing_build_dirs):
                    with open(refcount_file, 'w') as f:
                        for line in existing_build_dirs:
                            f.write(line)
                            f.write('\n')
                else:
                    local_edit = len(check_output(['svn', 'st', '-q', sandbox_dir]).decode('utf-8').split('\n')) > 1
                    if not local_edit:
                        rmtree(sandbox_dir)
                    else:
                        logger.warning(
                            'No build directory is using "%s" but, since it contains local modifications, it will not be garbage collected')


class Node:
    def __init__(self):
        self.children = set()


class Module(Node):
    repodir = expanduser('~/.quark')
    subproject_dir = None

    @staticmethod
    def _parse_fragment(url):
        res = {}
        for equality in url.fragment.split():
            index = equality.find('=')
            key = equality[:index]
            value = equality[index + 1:]
            res[key] = value
        return res

    @staticmethod
    def create(name=None, urlstring=None, options={}):

        if name is None or urlstring is None:
            res = Module(options=options)
        else:
            url = urlparse(urlstring)
            kwargs = dict(name=name, url=url, options=options)
            if url.scheme.startswith('git'):
                res = GitModule(**kwargs)
            elif url.scheme.startswith('svn'):
                res = SvnModule(**kwargs)
            else:
                raise ValueError("Unrecognized dependency for url '%s'", urlstring)
            res.urlstring = urlstring
            return res

    def __init__(self, name=None, options={}):
        super().__init__()
        self.name = name
        self.options = options
        self._directory = None
        self._checkout_directory = None

    def __hash__(self):
        return self.name.__hash__()

    def same_checkout(self, other):
        raise NotImplementedError()

    def checkout(self, *args, **kwargs):
        raise NotImplementedError()

    def update(self, *args, **kwargs):
        raise NotImplementedError()

    def local_edit(self, *args, **kwargs):
        raise NotImplementedError()

    @property
    def checkout_directory(self):
        if not self._checkout_directory:
            self._checkout_directory = join(self.repodir, md5(self.url.geturl().encode()).digest().hex())
        return self._checkout_directory

    @checkout_directory.setter
    def checkout_directory(self, checkout_directory):
        self._checkout_directory = checkout_directory

    @property
    def directory(self):
        if not self._directory:
            return join(self.subproject_dir, self.name)
        return self._directory

    @directory.setter
    def directory(self, directory):
        self._directory = directory


class GitModule(Module):
    @classproperty
    def repodir(cls):
        return join(Module.repodir, 'git')

    def __init__(self, name, url, options={}):
        super().__init__(name=name, options=options)
        self.ref = 'origin/HEAD'
        if url.fragment:
            fragment = Module._parse_fragment(url)
            if 'commit' in fragment:
                self.ref = fragment['commit']
            elif 'tag' in fragment:
                self.ref = fragment['tag']
            elif 'branch' in fragment:
                self.ref = 'origin/%s' % fragment['branch']
        self.url = url._replace(fragment='')._replace(scheme=url.scheme.replace('git+', ''))

    def same_checkout(self, other):
        if isinstance(other, GitModule) and (self.url, self.ref) == (other.url, other.ref):
            return True
        return False

    def check_origin(self):
        with DirectoryContext(self.directory):
            if check_output(['git', 'config', '--get', 'remote.origin.url']) != self.checkout_directory:
                if not self.has_local_edit():
                    logger.warning("%s is not a clone of %s "
                                   "but it hasn't local modifications, "
                                   "removing it..", self.directory, self.url.geturl())
                    rmtree(self.directory)
                    self.checkout()
                else:
                    raise ValueError(
                        "'%s' is not a clone of '%s' and has local"
                        " modifications, I don't know what to do with it..." %
                        self.directory, self.url.geturl())

    def checkout(self, *args, **kwargs):
        if not exists(self.checkout_directory):
            fork(['git', 'clone', '--mirror', self.url.geturl(), self.checkout_directory])
        else:
            with DirectoryContext(self.checkout_directory):
                fork(['git', 'fetch'])
        if not exists(self.directory):
            fork(['git', 'clone', self.checkout_directory, self.directory])
        if self.has_local_edit():
            logger.warning("Directory '%s' contains local modifications" % self.directory)
        with DirectoryContext(self.directory):
            fork(['git', 'fetch'])
            fork(['git', 'checkout', self.ref])

    def update(self, *args, **kwargs):
        with DirectoryContext(self.checkout_directory):
            fork(['git', 'fetch'])
        with DirectoryContext(self.directory):
            fork(['git', 'checkout', self.ref])

    def has_local_edit(self, *args, **kwargs):
        with DirectoryContext(self.directory):
            cmd = ['git', 'status', '--porcelain']
            with SubprocessContext(cmd, universal_newlines=True, stdout=PIPE, check=True) as pipe:
                for _ in pipe.stdout:
                    return True
        return False


class SvnModule(Module):
    @classproperty
    def repodir(cls):
        return join(Module.repodir, 'svn')

    def __init__(self, name, url, options={}):
        super().__init__(name, options=options)
        self.rev = 'HEAD'
        fragment = (url.fragment and Module._parse_fragment(url)) or {}
        rev = fragment.get('rev', None)
        branch = fragment.get('branch', None)
        tag = fragment.get('tag', None)
        if (branch or tag) and self.url.path.endswith('trunk'):
            url = url._replace(path=self.url.path[:-5])
        if branch:
            url = url._replace(path=join(url.path, 'branches', branch))
        elif tag:
            url = url._replace(path=join(url.path, 'tags', tag))
        if rev:
            url = url._replace(path=url.path + '@' + rev)
            self.rev = rev
        self.url = url._replace(fragment='')

    def same_checkout(self, other):
        if isinstance(other, SvnModule) and (self.url, self.rev) == (other.url, other.rev):
            return True
        return False

    def checkout(self, *args, **kwargs):
        fork(['svn', 'checkout', self.url.geturl(), self.checkout])
        os.symlink(self.checkout, self.directory)

    def update(self, *args, **kwargs):
        with DirectoryContext(self.directory):
            fork(['svn', 'up', '-r', self.rev])

    def has_local_edit(self, *args, **kwargs):
        xml = call(['svn', 'st', '--xml', self.directory], universal_newlines=True, stdout=PIPE)
        doc = etree.parse(xml)
        for entry in doc.xpath('/status/target[@path="%s"]/entry' % self.directory):
            return True
        return False


mkdir(Module.repodir)
mkdir(SvnModule.repodir)
mkdir(GitModule.repodir)
