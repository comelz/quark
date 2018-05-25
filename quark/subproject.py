import logging
import json
from os.path import exists, join
from shutil import rmtree
from subprocess import check_output, call, PIPE
from urllib.parse import urlparse

import xml.etree.ElementTree as ElementTree

from quark.utils import DirectoryContext, fork, SubprocessContext
from quark.utils import freeze_file, dependency_file, mkdir, load_conf, walk_tree

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
    def create(name, urlstring, directory, options, **kwargs):
        if not urlstring:
            return Subproject(name, directory, options, **kwargs)
        url = urlparse(urlstring)
        args = (name, url, directory, options)
        if url.scheme.startswith('git'):
            res = GitSubproject(*args, **kwargs)
        elif url.scheme.startswith('svn'):
            res = SvnSubproject(*args, **kwargs)
        else:
            raise ValueError("Unrecognized dependency for url '%s'", urlstring)
        res.urlstring = urlstring
        return res

    @staticmethod
    def create_dependency_tree(source_dir, url=None, options=None, update=False):
        subproject_dir = join(source_dir, 'lib')
        if url:
            root = Subproject.create(None, url, source_dir, options or {})
            root.checkout()
        else:
            root = Subproject(directory=source_dir, options=options or {})
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
                if update:
                    mod.update()
            else:
                if newmodule.exclude_from_cmake != mod.exclude_from_cmake:
                    children_conf = [join(parent.directory, dependency_file) for parent in mod.parents]
                    parent_conf = join(parent.directory, dependency_file)
                    raise ValueError("Conflicting value of 'exclude_from_cmake'"
                                     " attribute for module '%s': '%s' required by %s and %s required by %s" %
                                     (name, str(mod.exclude_from_cmake), children_conf, str(parent.exclude_from_cmake),
                                      parent_conf)
                                     )
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
            stack.append(mod)
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
            if current_module.external_project:
                generate_cmake_script(current_module.directory)
                continue
            conf = load_conf(current_module.directory)
            if conf:
                for name, depobject in conf.get('depends', {}).items():
                    external_project = depobject.get('external_project', False)
                    add_module(current_module, name,
                               freeze_dict.get(name, depobject.get('url', None)), depobject.get('options', {}),
                               exclude_from_cmake=depobject.get('exclude_from_cmake', external_project),
                               external_project=external_project
                               )
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
                                           freeze_dict.get(name, depobject.get('url', None)),
                                           depobject.get('options', {}))
        return root, modules

    def __init__(self, name=None, directory=None, options=None, exclude_from_cmake=False, external_project=False):
        super().__init__()
        self.name = name
        self.directory = directory
        self.options = options or {}
        self.exclude_from_cmake = exclude_from_cmake
        self.external_project = external_project

    def __hash__(self):
        return self.name.__hash__()

    def same_checkout(self, other):
        return True

    def checkout(self):
        raise NotImplementedError()

    def update(self):
        raise NotImplementedError()

    def local_edit(self):
        raise NotImplementedError()

    def url_from_checkout(self):
        raise NotImplementedError()

    def toJSON(self):
        return {
            "name": self.name,
            "children": [child.toJSON() for child in self.children],
            "options": self.options,
        }


class GitSubproject(Subproject):
    def __init__(self, name, url, directory, options, **kwargs):
        super().__init__(name, directory, options, **kwargs)
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
            if check_output(['git', 'config', '--get', 'remote.origin.url']) != self.url:
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
        fork(['git', 'clone', self.url.geturl(), self.directory])

    def update(self):
        if not exists(self.directory):
            self.checkout()
        elif self.has_local_edit():
            logger.warning("Directory '%s' contains local modifications" % self.directory)
        else:
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
            with SubprocessContext(['git', 'remote', 'get-url', 'origin'], universal_newlines=True, stdout=PIPE,
                                   check=True) as pipe:
                origin = pipe.stdout.read()[:-1]
            with SubprocessContext(['git', 'log', '-1', '--format=%H'], universal_newlines=True, stdout=PIPE,
                                   check=True) as pipe:
                commit = pipe.stdout.read()[:-1]
        return 'git+%s#commit=%s' % (origin, commit)


class SvnSubproject(Subproject):
    def __init__(self, name, url, directory, options, **kwargs):
        super().__init__(name, directory, options, **kwargs)
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
        fork(['svn', 'checkout', self.url.geturl(), self.directory])

    def update(self):
        if not exists(self.directory):
            self.checkout()
        elif self.has_local_edit():
            logger.warning("Directory '%s' contains local modifications" % self.directory)
        else:
            with DirectoryContext(self.directory):
                fork(['svn', 'switch', self.url.geturl()])
                # fork(['svn', 'up', '-r', self.rev])

    def has_local_edit(self):
        with SubprocessContext(['svn', 'st', '--xml', self.directory], universal_newlines=True, stdout=PIPE,
                               check=True) as pipe:
            doc = ElementTree.parse(pipe.stdout)
        for entry in doc.findall('./status/target/entry[@path="%s"]/entry[@item="modified"]' % self.directory):
            return True
        return False

    def url_from_checkout(self):
        with SubprocessContext(['svn', 'info', '--xml', self.directory], universal_newlines=True, stdout=PIPE,
                               check=True) as pipe:
            doc = ElementTree.parse(pipe.stdout)
        return doc.findall('./entry/url')[0].text + "@" + doc.findall('./entry/commit')[0].get('revision')


def generate_cmake_script(source_dir, url=None, options=None, print_tree=False):
    root, modules = Subproject.create_dependency_tree(source_dir, url, options, update=True)
    subproject_dir = join(source_dir, 'lib')
    if print_tree:
        print(json.dumps(root.toJSON(), indent=4))
    with open(join(subproject_dir, 'CMakeLists.txt'), 'w') as cmake_lists_txt:
        processed = {None}

        def cb(module):
            if module.name in processed or module.exclude_from_cmake or not exists(
                    join(module.directory, "CMakeLists.txt")):
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
