import logging
from os.path import exists, join
from shutil import rmtree
from subprocess import check_output, call, PIPE
from urllib.parse import urlparse

from lxml import etree

from quark.utils import DirectoryContext, fork, SubprocessContext

logger = logging.getLogger(__name__)


class Node:
    def __init__(self):
        self.parents = set()
        self.children = set()


class Subproject(Node):
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
    def create(name, urlstring, directory):
        url = urlparse(urlstring)
        args = (name, url, directory)
        if url.scheme.startswith('git'):
            res = GitSubproject(*args)
        elif url.scheme.startswith('svn'):
            res = SvnSubproject(*args)
        else:
            raise ValueError("Unrecognized dependency for url '%s'", urlstring)
        res.urlstring = urlstring
        return res

    def __init__(self, name=None, directory=None):
        super().__init__()
        self.name = name
        self.directory = directory

    def __hash__(self):
        return self.name.__hash__()

    def same_checkout(self, other):
        raise NotImplementedError()

    def checkout(self):
        raise NotImplementedError()

    def update(self):
        raise NotImplementedError()

    def local_edit(self):
        raise NotImplementedError()

    def url_from_checkout(self):
        raise NotImplementedError()


class GitSubproject(Subproject):
    def __init__(self, name, url, directory):
        super().__init__(name, directory)
        self.ref = 'origin/HEAD'
        if url.fragment:
            fragment = Subproject._parse_fragment(url)
            if 'commit' in fragment:
                self.ref = fragment['commit']
            elif 'tag' in fragment:
                self.ref = fragment['tag']
            elif 'branch' in fragment:
                self.ref = 'origin/%s' % fragment['branch']
        self.url = url._replace(fragment='')._replace(scheme=url.scheme.replace('git+', ''))

    def same_checkout(self, other):
        if isinstance(other, GitSubproject) and (self.url, self.ref) == (other.url, other.ref):
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

    def checkout(self):
        if not exists(self.directory):
            fork(['git', 'clone', self.url.geturl(), self.directory])
        elif self.has_local_edit():
            logger.warning("Directory '%s' contains local modifications" % self.directory)
        with DirectoryContext(self.directory):
            fork(['git', 'fetch'])
            fork(['git', 'checkout', self.ref])

    def update(self):
        with DirectoryContext(self.directory):
            fork(['git', 'fetch'])
            fork(['git', 'checkout', self.ref])

    def has_local_edit(self):
        with DirectoryContext(self.directory):
            cmd = ['git', 'status', '--porcelain']
            with SubprocessContext(cmd, universal_newlines=True, stdout=PIPE, check=True) as pipe:
                for _ in pipe.stdout:
                    return True
        return False

    def url_from_checkout(self):
        with DirectoryContext(self.directory):
            origin = call(['git', 'remote', 'get-url', 'origin'], universal_newlines=True, stdout=PIPE)
            commit = call(['git', 'log', '-1', '--format=%H'], universal_newlines=True, stdout=PIPE)
        return 'git+%s#commit=%s' % (origin, commit)


class SvnSubproject(Subproject):
    def __init__(self, name, url, directory):
        super().__init__(name, directory)
        self.rev = 'HEAD'
        fragment = (url.fragment and Subproject._parse_fragment(url)) or {}
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
        if isinstance(other, SvnSubproject) and (self.url, self.rev) == (other.url, other.rev):
            return True
        return False

    def checkout(self):
        if not exists(self.directory):
            fork(['svn', 'checkout', self.url.geturl(), self.directory])
        elif self.has_local_edit():
            logger.warning("Directory '%s' contains local modifications" % self.directory)
        else:
            with DirectoryContext(self.directory):
                fork(['svn', 'switch', self.url.geturl()])

    def update(self):
        with DirectoryContext(self.directory):
            fork(['svn', 'up', '-r', self.rev])

    def has_local_edit(self):
        with SubprocessContext(['svn', 'st', '--xml', self.directory], universal_newlines=True, stdout=PIPE,
                               check=True) as pipe:
            doc = etree.parse(pipe.stdout)
        for entry in doc.xpath('/status/target/entry[@path="%s"]/entry[@item="modified"]' % self.directory):
            return True
        return False

    def url_from_checkout(self):
        with SubprocessContext(['svn', 'info', '--xml', self.directory], universal_newlines=True, stdout=PIPE, check=True) as pipe:
            doc = etree.parse(pipe.stdout)
        return doc.xpath('/info/entry/url')[0].text + "@" + doc.xpath('/info/entry/commit')[0].get('revision')
