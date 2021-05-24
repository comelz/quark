import logging
import json
import os
from os.path import exists, join, isdir
from shutil import rmtree
from subprocess import call, PIPE, Popen, CalledProcessError, run
from urllib.parse import urlparse
from quark.utils import cmake_escape
import shutil

import xml.etree.ElementTree as ElementTree

from quark.utils import DirectoryContext as cd, fork, log_check_output
from quark.utils import freeze_file, dependency_file, mkdir, load_conf

logger = logging.getLogger(__name__)

class QuarkError(RuntimeError):
    pass

def vcs_class(directory):
    if exists(join(directory, ".svn")):
        cls = SvnSubproject
    elif exists(join(directory, ".git")):
        cls = GitSubproject
    else:
        raise QuarkError("Couldn't detect repository type for directory %s" % directory)
    return cls

def url_from_directory(directory, include_commit = True):
    return vcs_class(directory).url_from_directory(directory, include_commit)

def not_a_project(directory, proj_type):
    raise QuarkError("""

Directory '%s' isn't a %s sandbox,
but it's marked as such in a subproject.quark.

Either:
- it was previously a subproject of a different kind (e.g. the catalog changed
  it from Subversion to Git);
- it's committed in the root project;
- it's a local modification.

Please remove it and re-run quark up.
""" % (directory, proj_type))

class Subproject:
    def get_env_variables(self, toplevel):
        sm_path = os.path.relpath(self.directory, toplevel)
        displaypath = os.path.relpath(self.directory, toplevel)

        return {
            # the name of the submodule
            "name": self.name,
            # the path of the submodule from the immediate superproject
            "sm_path": sm_path,
            # the relative path of the module from the actual working directory
            "displaypath": displaypath,
            # the directory of the immediate superproject
            "toplevel": toplevel
        }

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
    def create(name, urlstring, directory, options, conf = {}, **kwargs):
        url = urlparse(urlstring)
        args = (name, url, directory, options, conf)
        if urlstring is None:
            # fake project, used for non-versioned root
            res = Subproject(name, directory, options, conf, **kwargs)
        elif url.scheme.startswith('git'):
            res = GitSubproject(*args, **kwargs)
        elif url.scheme.startswith('svn'):
            res = SvnSubproject(*args, **kwargs)
        else:
            raise ValueError("Unrecognized dependency for url '%s'" % (urlstring,))
        res.urlstring = urlstring
        return res

    @staticmethod
    def create_dependency_tree(source_dir, url=None, options=None, update=False, clean=False):
        # make sure the separator is present
        source_dir_rp = os.path.join(os.path.abspath(source_dir), '')
        root_url = url
        try:
            root_url = url_from_directory(source_dir)
        except QuarkError:
            pass
        root = Subproject.create("root", root_url, source_dir, {}, {}, toplevel = True)
        if url and update:
            root.checkout()
        conf = load_conf(source_dir)
        if conf is None:
            return root, {}
        subprojects_dir = conf.get("subprojects_dir", 'lib')
        subproject_dir = join(source_dir, subprojects_dir)
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

        def add_module(parent, name, uri, options, conf, **kwargs):
            if uri is None:
                # options add only, lookup from existing modules
                uri = modules[name].urlstring
            target_dir = join(subproject_dir, name)
            target_dir_rp = os.path.join(os.path.abspath(target_dir), '')
            if not target_dir_rp.startswith(source_dir_rp):
                raise QuarkError("""
Subproject `%s` (URI: %s)
is trying to escape from the main project directory (`%s`)
subproject abspath:   %s
main project abspath: %s""" % (name, uri, source_dir, target_dir_rp, source_dir_rp))
            newmodule = Subproject.create(name, uri, target_dir, options, conf, **kwargs)
            mod = modules.setdefault(name, newmodule)
            if mod is newmodule:
                mod.parents.add(parent)
                if update:
                    mod.update(clean)
            else:
                if newmodule.exclude_from_cmake != mod.exclude_from_cmake:
                    children_conf = [join(parent.directory, dependency_file) for parent in mod.parents]
                    parent_conf = join(parent.directory, dependency_file)
                    raise ValueError("Conflicting value of 'exclude_from_cmake'"
                                     " attribute for module '%s': %r required by %s and %r required by %s" %
                                     (name, mod.exclude_from_cmake, children_conf, newmodule.exclude_from_cmake,
                                      parent_conf)
                                     )
                if not newmodule.same_checkout(mod) and uri is not None:
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
        if update:
            mkdir(subproject_dir)
        while len(stack):
            current_module = stack.pop()
            if current_module.external_project:
                init_subprojects_dir(current_module.directory, update = update)
                continue
            conf = load_conf(current_module.directory)
            if conf:
                if current_module.toplevel:
                    current_module.options = conf.get('toplevel_options', {})
                    if options:
                        current_module.options.update(options)

                def do_add_module(name, depobject):
                    external_project = depobject.get('external_project', False)
                    add_module(current_module, name,
                               freeze_dict.get(name, depobject.get('url', None)),
                               depobject.get('options', {}),
                               depobject,
                               exclude_from_cmake=depobject.get('exclude_from_cmake', external_project),
                               external_project=external_project
                               )

                for name, depobject in conf.get('depends', {}).items():
                    do_add_module(name, depobject)
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
                                do_add_module(name, depobject)
        root.set_local_ignores(subprojects_dir, modules.values())
        return root, modules

    def __init__(self, name=None, directory=None, options=None, conf = {}, exclude_from_cmake=False, external_project=False, toplevel = False):
        self.conf = conf
        self.parents = set()
        self.children = set()
        self.name = name
        self.directory = directory
        self.options = options or {}
        self.exclude_from_cmake = exclude_from_cmake
        self.external_project = external_project
        self.toplevel = toplevel

    def __hash__(self):
        return self.name.__hash__()

    def same_checkout(self, other):
        return True

    def checkout(self):
        raise NotImplementedError()

    def update(self, clean=False):
        raise NotImplementedError()

    def status(self):
        print("Unsupported external %s" % self.directory)

    def local_edit(self):
        raise NotImplementedError()

    def url_from_checkout(self, *args, **kwargs):
        return self.url_from_directory(directory = self.directory, *args, **kwargs)

    def mirror(self, dest):
        raise NotImplementedError()

    def toJSON(self):
        return {
            "name": self.name,
            "children": [child.toJSON() for child in self.children],
            "options": self.options,
        }

    def set_local_ignores(self, subprojects_dir, modules):
        pass

class GitSubproject(Subproject):
    def get_env_variables(self, toplevel):
        return {
            **super().get_env_variables(toplevel=toplevel),
            **{
                "sha1": str(self.ref),
                "version_control": "git"
            }
        }

    def __init__(self, name, url, directory, options, conf = {}, **kwargs):
        super().__init__(name, directory, options, conf, **kwargs)
        # Let's assume that origin/HEAD points to a branch, anything else would be madness
        self.ref_type = 'branch'
        self.ref = 'origin/HEAD'
        if url.fragment:
            fragment = Subproject._parse_fragment(url)
            if 'commit' in fragment:
                self.ref = fragment['commit']
                self.ref_type = 'commit'
            elif 'tag' in fragment:
                self.ref = fragment['tag']
                self.ref_type = 'tag'
            elif 'branch' in fragment:
                self.ref = 'origin/%s' % fragment['branch']
        self.url = url._replace(fragment='')._replace(scheme=url.scheme.replace('git+', ''))

    def same_checkout(self, other):
        if isinstance(other, GitSubproject) and (self.url, self.ref, self.conf.get("shallow", False)) == (other.url, other.ref, other.conf.get("shallow", False)):
            return True
        return False

    def noremote_ref(self):
        nr_ref = self.ref
        if '/' in nr_ref:
            nr_ref = nr_ref.split('/', 1)[1]
        return nr_ref


    def checkout(self):
        shallow = self.conf.get("shallow", False)

        if self.ref_type == 'commit' and shallow:
            # We cannot straight clone a shallow repo using a commit hash (-b doesn't support it)
            # do the dance described at https://stackoverflow.com/a/43136160/214671
            os.mkdir(self.directory)
            with cd(self.directory):
                fork(['git', 'init'])
                fork(['git', 'remote', 'add', 'origin', self.url.geturl()])
                fork(['git', 'fetch', '--depth', '1', 'origin', self.noremote_ref()])
                fork(['git', 'checkout', self.ref, '--'])
        else:
            # Regular case
            extra_opts = []
            if shallow:
                extra_opts += ["--depth", "1"]
            # Needed essentially for the shallow case, as for full clones the
            # git clone -n + git checkout would suffice
            if shallow and self.ref_type != 'commit' and self.ref != 'origin/HEAD':
                extra_opts += ['-b', self.noremote_ref()]
            fork(['git', 'clone', '-n'] + extra_opts + ['--', self.url.geturl(), self.directory])
            with cd(self.directory):
                opts = [self.ref]
                # If it's a branch, create a remote-tracking one
                if self.ref_type == 'branch' and not shallow:
                    # Find out a sensible local branch name (needed for origin/HEAD)
                    local_branch = self.symbolic_full_name(self.ref).split('/origin/', 1)[1]
                    opts = [ local_branch ]
                fork(['git', 'checkout'] + opts + ['--'])

    def update(self, clean=False):
        def actualUpdate():
            with cd(self.directory):
                try:
                    current_origin = log_check_output(['git', 'config', '--get', 'remote.origin.url']).strip().decode('utf-8')
                except CalledProcessError:
                    current_origin = None
                if current_origin != self.url.geturl():
                    # For now we just throw a fit; it shouldn't happen often,
                    # and in this case there's no "right" answer - the repo may
                    # have just moved, or we may be dealing with a completely
                    # unrelated repo.
                    # In future, it would be nice to be a bit more interactive
                    raise QuarkError("""

Directory '%s' is a git repository,
but its remote 'origin' (%r)
does not match what we expect (%r).

Please either remove the local clone, or fix its remote.""" % (self.directory, current_origin, self.url.geturl()))
                if self.conf.get("shallow", False):
                    # git fetch with shallow clones isn't very smart, and
                    # re-fetches stuff that we already have; try to avoid this

                    # FIXME: the current approach means that shallow clones
                    # will be in detached HEAD state to a commit pretty much
                    # always.
                    # Probably this is not a big problem because shallow repos
                    # in Quark aren't meant to be used for actual repo work,
                    # and the previous implementation always had FETCH_HEAD
                    # checked out; however, in future it would be nice to have
                    # a cleaner solution.

                    if self.ref_type == 'commit':
                        # Easy case: we already know exactly the commit we need
                        remote_commit = self.ref
                    else:
                        # Ask the remote what we are expected to have here
                        remote_commit = log_check_output(['git', 'ls-remote', 'origin', self.noremote_ref()]).split(b'\t')[0].strip().decode('utf-8')

                    try:
                        # Try to check it out; in the common case (nothing
                        # changed) this should be a no-op
                        fork(['git', 'checkout', remote_commit, '--'])
                    except CalledProcessError:
                        # Probably we don't have the commit; fetch it
                        fork(['git', 'fetch', '--depth', '1', 'origin', remote_commit])
                        # Try again
                        fork(['git', 'checkout', remote_commit, '--'])
                else:
                    fork(['git', 'fetch'])
                    # If we want to go on a branch, try to find a local branch that tracks it
                    # and use it (possibly with a fast-forward)
                    if self.ref_type == 'branch':
                        # Resolve the remote ref
                        remote_fullref = self.symbolic_full_name(self.ref)
                        # Get a sensible local branch name to try
                        local_ref = remote_fullref.split('/origin/', 1)[1]
                        # Check if it is actually tracking our target
                        try:
                            local_fulltrackref = self.symbolic_full_name(local_ref + "@{u}")
                        except CalledProcessError:
                            # It's fine if it fails - we may not have a local-tracking branch,
                            # so git checkout will do the right thing here
                            local_fulltrackref = remote_fullref

                        if remote_fullref == local_fulltrackref:
                            try:
                                # Checkout and fast-forward
                                fork(['git', 'checkout', local_ref, '--'])
                                fork(['git', 'merge', '--ff-only', self.ref, '--'])
                                # Final sanity check
                                if log_check_output(['git', 'rev-parse', self.ref, '--']) != log_check_output(['git', 'rev-parse', local_ref, '--']):
                                    logger.warning("Warning: your local branch is ahead of required remote branch!")
                                return
                            except CalledProcessError:
                                logger.warning("Couldn't fast-forward local branch, fallback to detached head mode...")
                    # General case: plain checkout of the origin ref (going in detached HEAD)
                    fork(['git', 'checkout', self.ref, '--'])

        if not exists(self.directory):
            self.checkout()
        elif not exists(self.directory + "/.git"):
            not_a_project(self.directory, "Git")
        elif self.has_local_edit():
            if clean:
                self.clean_all()
                actualUpdate()
            else:
                logger.warning("Directory '%s' contains local modifications" % self.directory)
                self.stash()
                actualUpdate()
                self.pop()
        else:
            actualUpdate()

    def stash(self):
        with cd(self.directory):
            fork(['git', 'stash', '--all'])

    def pop(self):
        with cd(self.directory):
            fork(['git', 'stash', 'pop'])

    def clean_all(self):
        with cd(self.directory):
            fork(['git', 'clean', '-fd'])

    def status(self):
        fork(['git', "--git-dir=%s/.git" % self.directory, "--work-tree=%s" % self.directory, 'status'])

    def has_local_edit(self):
        with cd(self.directory):
            return log_check_output(['git', 'status', '--porcelain']) != b""

    def symbolic_full_name(self, ref):
        with cd(self.directory):
            return log_check_output(['git', 'rev-parse', '--symbolic-full-name', ref, '--']).split(b'\n')[0].strip().decode('utf-8')

    @staticmethod
    def url_from_directory(directory, include_commit = True):
        with cd(directory):
            origin = log_check_output(['git', 'remote', 'get-url', 'origin'], universal_newlines=True)[:-1]
            commit = log_check_output(['git', 'log', '-1', '--format=%H'], universal_newlines=True)[:-1]
        ret = 'git+%s' % (origin,)
        if include_commit:
            ret += '#commit=%s' % (commit,)
        return ret

    def mirror(self, dst_dir):
        source_dir = self.directory
        def mkdir_p(path):
            if path.strip() != '' and not os.path.exists(path):
                os.makedirs(path)

        env = os.environ.copy()
        env['LC_MESSAGES'] = 'C'

        def tracked_files():
            p = Popen(['git', 'ls-tree', '-r', '--name-only', 'HEAD'], stdout=PIPE, env=env)
            out = p.communicate()[0]
            if p.returncode != 0 or not out.strip():
                return None
            return [e.strip() for e in out.splitlines() if os.path.exists(e)]

        def cp(src, dst):
            r, f = os.path.split(dst)
            mkdir_p(r)
            shutil.copy2(src, dst)

        with cd(source_dir):
            for t in tracked_files():
                cp(t, os.path.join(dst_dir, t.decode()))

    def set_local_ignores(self, subprojects_dir, modules):
        BEGIN = "# Following lines automatically generated by quark"
        END = "# Previous lines automatically generated by quark"
        # .git/info may not exist
        exclude_path_dir = os.path.join(self.directory, ".git", "info")
        try:
            os.makedirs(exclude_path_dir, exist_ok = True)
        except NotADirectoryError:
            # If we are in a working tree created with 'git worktree add' then
            # .git is a file, not a dir, and the makedirs function fails.
            # Unfortunately git doesn't support different info/exclude files
            # for different working trees connected to the same local repo, so
            # we just warn the user and do nothing: note that this implies that
            # the exclude file used for the additional working trees is the
            # same created for the main working tree (if any).
            logger.warning("Couldn't set local ignore list. If '%s' is a "
                    "worktree this is expected and the info/exclude file of "
                    "the main working tree will be used." % self.directory)
            return
        exclude_path = os.path.join(exclude_path_dir, "exclude")

        quark_exclude_path = exclude_path+".quark"

        written = False

        def write_excludes(fd):
            if modules:
                fd.write(BEGIN + "\n")
                for m in modules:
                    # 1. normalize
                    # 2. make it relative to the root of the repo (so the repo is movable)
                    # 3. make sure it has a / at the end; this ensures that git treates it like a path
                    #    and not like a glob pattern
                    fd.write(
                            os.path.join(
                                os.path.relpath(
                                    os.path.normpath(m.directory),
                                    self.directory),
                                "") + "\n")
                fd.write(os.path.join(subprojects_dir, "CMakeLists.txt") + "\n")
                fd.write(END + "\n")

        with open(quark_exclude_path, "w") as new_exc:
            try:
                # Copy the original file, skipping our output from the last run
                with open(exclude_path, "r") as old_exc:
                    skip=False
                    for L in old_exc:
                        LS = L.strip()
                        if LS == BEGIN:
                            skip = True
                            # If the excludes were already present, re-write
                            # them in the same position (the user may want to
                            # force our patterns in a particular position, as
                            # order matters)
                            if not written:
                                write_excludes(new_exc)
                                written = True
                        if not skip:
                            new_exc.write(L)
                        if LS == END:
                            skip = False
            except IOError:
                pass

            # If they weren't written, write them out at the end
            if not written:
                write_excludes(new_exc)

        # Replace the old with the new
        os.replace(quark_exclude_path, exclude_path)

class SvnSubproject(Subproject):
    def get_env_variables(self, toplevel):
        return {
            **super().get_env_variables(toplevel=toplevel),
            **{
                "rev": str(self.rev),
                "version_control": "svn"
            }
        }

    def __init__(self, name, url, directory, options, conf = {}, **kwargs):
        super().__init__(name, directory, options, conf = {}, **kwargs)
        self.rev = 'HEAD'
        fragment = (url.fragment and Subproject._parse_fragment(url)) or {}
        if len(fragment):
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
        else:
            if '@' in url.path:
                self.rev = url.path.split('@')[-1]
        self.url = url._replace(fragment='')

    def same_checkout(self, other):
        if isinstance(other, SvnSubproject) and (self.url, self.rev) == (other.url, other.rev):
            return True
        return False

    def checkout(self):
        fork(['svn', 'checkout', self.url.geturl(), self.directory])

    def update(self, clean=False):
        if not exists(self.directory):
            self.checkout()
        elif not exists(self.directory + "/.svn"):
            not_a_project(self.directory, "Subversion")
        else:
            with cd(self.directory):
                if self.has_local_edit():
                    if clean:
                        fork(['svn', 'revert', '-R', '.'])
                        fork(['svn', 'cleanup', '--remove-unversioned', '.'])
                    else:
                        logger.warning("Directory '%s' contains local modifications" % self.directory)
                # svn switch _would be ok_ even just to perform an update, but,
                # unlike svn up, it touches the timestamp of all the files,
                # forcing full rebuilds; so, if we are already on the correct
                # url just use svn up

                # Notice that, unlike other svn commands, -r in svn up works as
                # a peg revision (the @ syntax), so it takes the URL of the
                # current working copy and looks it up in the repository _as it
                # was at the requested revision_ (or HEAD if none is specified)
                target_base,target_rev = (self.url.geturl().split('@') + [''])[:2]
                if target_base == self.url_from_checkout(include_commit = False):
                    fork(['svn', 'up'] + (["-r" + target_rev] if target_rev else []))
                else:
                    fork(['svn', 'switch', self.url.geturl()])

    def status(self):
        fork(['svn', 'status', self.directory])

    def has_local_edit(self):
        xml = log_check_output(['svn', 'st', '--xml', self.directory], universal_newlines=True)
        doc = ElementTree.fromstring(xml)
        return len(doc.findall('./target/entry/wc-status[@item="modified"]')) != 0

    @staticmethod
    def url_from_directory(directory, include_commit = True):
        xml = log_check_output(['svn', 'info', '--xml', directory], universal_newlines=True)
        doc = ElementTree.fromstring(xml)
        ret = doc.findall('./entry/url')[0].text
        if include_commit:
            ret += "@" + doc.findall('./entry/commit')[0].get('revision')
        return ret

    def mirror(self, dst, quick = False):
        import shutil
        src = self.directory

        os.chdir(src)
        if not quick and isdir(dst):
            shutil.rmtree(dst)
        if not isdir(dst):
            os.makedirs(dst)

        # Forziamo il locale a inglese, perché parseremo l'output di svn e non
        # vogliamo errori dovuti alle traduzioni.
        env = os.environ.copy()
        env["LC_MESSAGES"] = "C"

        dirs = ["."]

        # Esegue svn info ricorsivamente per iterare su tutti i file versionati.
        for D in dirs:
            infos = {}
            for L in Popen(["svn", "info", "--recursive", D], stdout=PIPE, env=env).stdout:
                L = L.decode()
                if L.strip():
                    k,v = L.strip().split(": ", 1)
                    infos[k] = v
                else:
                    if infos["Schedule"] == "delete":
                        continue
                    fn = infos["Path"]
                    infos = {}
                    if fn == ".":
                        continue
                    fn1 = join(src, fn)
                    fn2 = join(dst, fn)
                    if isdir(fn1):
                        if not isdir(fn2):
                            os.makedirs(fn2)
                    elif not quick or newer(fn1, fn2):
                        shutil.copy2(fn1, fn2)

    def set_local_ignores(self, subprojects_dir, modules):
        # Svn doesn't support local sandbox ignore lists
        pass

def generate_clang_format(subprojects_dir):
    clangformat_data = """{
"DisableFormat": true,
"SortIncludes": false
}
"""
    with open(join(subprojects_dir, '.clang-format'), 'w') as f:
        f.write(clangformat_data)

def generate_cmake_script(subproject_dir, root):
    cmakelists_rows = []
    processed = set()

    def dump_options(module):
        for key, value in sorted(module.options.items()):
            if value is None:
                cmakelists_rows.append('unset(%s CACHE)\n' % (key))
                continue
            elif isinstance(value, bool):
                kind = "BOOL"
                value = 'ON' if value else 'OFF'
            else:
                kind = "STRING"
            cmakelists_rows.append('set(%s %s CACHE INTERNAL "" FORCE)\n' % (key, value))

    def process_module(module):
        # notice: if a module is marked as excluded from cmake we also
        # exclude its dependencies; they are nonetheless included if they
        # are required by another module which is not excluded from cmake
        if module.name in processed or module.exclude_from_cmake:
            return
        processed.add(module.name)
        # first add the dependent modules
        # module.children is a set, whose iteration order changes from run to run
        # make this deterministic (we want to generate always the same CMakeLists.txt)
        for c in sorted(module.children, key = lambda x: x.name):
            process_module(c)
        # dump options and add to the generated CMakeLists.txt
        dump_options(module)
        if module is not root:
            subdir = os.path.relpath(module.directory, subproject_dir)
            if exists(join(module.directory, "quark.cmake")):
                cmakelists_rows.append('include(%s)\n' % cmake_escape(join(subdir, "quark.cmake")))
            elif exists(join(module.directory, "CMakeLists.txt")):
                cmakelists_rows.append('add_subdirectory(%s)\n' % cmake_escape(subdir))

    process_module(root)

    # write only if different
    cmakelists_data = ''.join(cmakelists_rows)
    try:
        with open(join(subproject_dir, 'CMakeLists.txt'), 'r') as f:
            if cmakelists_data == f.read():
                # nothing to do, avoid touching the file (which often yields a full rebuild)
                return
    except IOError:
        pass
    # actually write the file
    with open(join(subproject_dir, 'CMakeLists.txt'), 'w') as f:
        f.write(cmakelists_data)

def init_subprojects_dir(source_dir, url=None, options=None, print_tree=False,update=True, clean=False):
    root, modules = Subproject.create_dependency_tree(source_dir, url, options, update=update, clean=clean)
    if print_tree:
        print(json.dumps(root.toJSON(), indent=4))
    conf = load_conf(source_dir)
    if update and conf is not None:
        subproject_dir = join(source_dir, conf.get("subprojects_dir", 'lib'))

        generate_cmake_script(subproject_dir, root)
        generate_clang_format(subproject_dir)

