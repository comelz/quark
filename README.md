# Quark #

Quark is a simple project dependency management system that works at source code level, although it can be used to fetch binary assets as well.

***Disclaimer:** the manual is still incomplete, but piutost che nient l'è mei piutost.*

## Name ##

For some reason, the original author was interested in the [Meson build system](https://mesonbuild.com/) when writing this tool, and it was thought that Quark would have been a nice companion. Other than that, there's no relation between them (indeed, it turns out that there's zero support for Meson in Quark).

# tl;dr quick-start user guide #

> Note: all commands specified throughout this document must be executed in the root directory of the top-level project unless otherwise specified; it is assumed that `quark` is in the `PATH`, although that's not strictly necessary (it's just more convenient).

## Installing ##

Quark is a pure Python 3 tool with zero dependencies outside of the standard library, so no real "installation" is required; in general, virtually all its developers just have a git clone of this repository and either

- add the `bin` subdirectory to the `PATH` (where an executable `quark` is provided for POSIX systems and a `quark.cmd` wrapper is there as well for the poor souls - and for the CI machines - using Windows),
- or add a symlink to `bin/quark` in some directory that is already in the `PATH` (e.g. `~/bin`)

The promise here is that in general Quark will only ever provide subcommands to the single `quark` command.

In general there's no particular assumption about where the repository clone is situated, or whether it is in the `PATH` at all; on CI machines it can be cloned on the fly and referred to as e.g. `./quark-clone/bin/quark`.

That being said, a `setup.py` is provided, so if you insist you can install it with `pip`

    pip3 install https://github.com/comelz/quark/archive/master.zip

just be aware that it's stuff that is not actively tested.

## Fetching dependencies of a quark-based project ##

    quark up

This reads `subprojects.quark` and fetches the latest version of the dependencies recursively (or the versions specified in `freeze.quark`, if present). If the checkouts/clones of the dependencies are already present, they are updated and possibly adjusted to point to the expected revision (`git fetch`/`git checkout` or `svn up -r`/`svn switch`).

## Freezing the currently-checked out dependencies ##

    quark freeze

A `freeze.quark` file is generated; if you want to keep it (e.g. if you are creating a tag of your project) just commit it to your VCS.

## Unfreezing the dependencies ##

Remove `freeze.quark`, then possibly run `quark up` to update the dependencies to the latest version.

# Full, project-owner guide #

## Goals and assumptions ##

Quark strives to solve these problems:

- **fetching project dependencies _from different VCS_** - namely, Subversion and git, allowing painless, gradual migration from an `svn:externals`-based world;
- **handling automatically recursive dependencies**, so that if project `A` depends from project `B`, it does not need to know about `B`'s dependencies;
- **handling conditional dependencies** (and their consequences on the dependencies graph), so that if `B` needs `C` only if a certain `B` feature is enabled, `C` isn't dragged in when it's not needed (either just to avoid wasting bandwidth/disk space, or even because such dependency isn't supported by a toolchain used to compile `A`);
- **providing dependencies information to build systems**, in particular (as of today) CMake; if `A` depends from `B` and `D` and `B` depends from `C`, the relevant `add_subdirectories` should be automatically generated _in the correct order_ (= they should be topologically sorted), to avoid duplicating the dependencies declarations both in the dependencies file and in the build system;
- **providing a convenient way to "freeze" floating dependencies** e.g. to archive the current state of the project for a tag;
- optionally, **allowing for a central catalog** to provide a name&rarr;location mapping for dependencies.

To tackle these challenges in a relatively simple fashion, some assumptions about projects are made; in particular:

- **one project = one repository = one set of dependencies** (although there's some second class support for "clusters" of projects; look for `toplevel_project` later in the document);
- **`subprojects.quark`**, the file containing the dependency information about the project, **must be in the root directory of each project** (although it can be missing; in this case, the project is assumed not to have dependencies);
- **all dependencies are fetched _in the same directory_**; this seems to be the only sane way to handle recursive dependencies that may be shared between multiple subprojects without going mad;
- **all projects that refer to some dependency must agree on its definition**, so the location must match and the options must not conflict;
- **authentication or repo-specific options are not any of Quark's business**; URLs of target repositories are passed straight to `git` or `svn`; if any particular extra option is needed to connect to some repository (e.g. a custom user-name or ssh key) it must be handled at `.ssh/config` level or `svn`/`git` configuration.

## Usage and features ##

Any quark-enabled project contains a `subprojects.quark` file in its root. It is a JSON file containing the dependencies, their options and in general Quark-related project options.

### Plain dependencies ###

A simple `subprojects.quark` for a top-level project (let's call it *blur-app*) may look like:

```
{
    "description": "blur-app subprojects.quark",
    "depends": [
        "blurlib":    { "url": "svn+ssh://svn.example.com/svn/blurlib/trunk" },
        "widgetslib": { "url": "git+ssh://git@git.example.com/widgets-inc/widgets.git" },
        "imagelib":   { "url": "svn+ssh://svn.example.com/svn/imagelib/trunk" }
    ]
}
```

and let's suppose `blurlib`'s `subprojects.quark` be like:

```
{
    "description": "blurlib subprojects.quark",
    "depends": [
        "imagelib":  { "url": "svn+ssh://svn.example.com/svn/imagelib/trunk" },
        "mathlib":   { "url": "svn+ssh://svn.another.example.com/svn/mathlib/trunk" }
    ]
}
```
> Note: the `"description"` field has no particular significance to Quark; throughout this document I'm just using it to hold comments because JSON stubbornly doesn't allow for comments.

We suppose instead that `widgetslib` has no `subprojects.quark`.

In this example, we can see that, at bare minimum, each dependency should have

- **a _name_**, which is the key in the `depends` object; it is used
    - to uniquely identify the dependency across the whole dependency tree (i.e., everybody referring to `imagelib` must be referring to the same thing);
    - to determine the name of the directory where the checked-out dependency is placed;
- **an _url_**, which specifies where the project is located, plus possibly which branch/tag/commit; more details about the exact syntax in a moment. Notice that this may not necessarily be provided explicitly, but may come implicitly through the *catalog* (explained in a later section).

When performing `quark up` in our *blur-app* top-level directory, Quark will extract (or update, if already present) all the dependencies specified in `subprojects.quark`, discovering and extracting recursive dependencies as it goes and building a dependency tree in the process. At the end, a `lib` directory will have been created, containing:

```
lib
├── CMakeLists.txt
├── blurlib
├── widgetslib
├── imagelib
└── mathlib
```

> Note: the target directory for dependencies can be altered specifying a custom subdirectory in the `"subprojects_dir"` key, as in:
>
> ```
> {
>     "subprojects_dir": "some_other_lib_directory",
>     "depends": ...
> ```

> Note: an implementation detail allows using relative paths in names, which enable a dirty hack to put single subprojects outside the subprojects directory (and path traversal attacks in malicious cases); this probably won't be fixed (as long as the final target stays in the project directory) for compatibility reasons, but is strongly discouraged.

As can be seen, all dependencies have been "flattened" into a single directory, and, even though `imagelib` is referenced both by `blurlib` and by `blur-app`, a single copy has been extracted. This is nice for bandwidth/disk usage, but most importantly ensures that there's only one version of each library.

For this to be possible, when discovering dependencies Quark ensures that a given library is defined univocally; if two subprojects refer to a dependency with the same name, but with different URLs (or other incompatible options), the checkout is aborted.

Also, a `CMakeLists.txt` has been generated that refers to all the subprojects in the correct (topologically-sorted) order; more on this later.

### Project URL format and VCS-specific quirks ###

Quark refers to project URLs in various places, most importantly in the `"url"` field of dependency objects and in the `freeze.quark` file; a project URL identifies the VCS to use to fetch the project, the location where the project is stored down to the branch/tag/commit to extract.

The protocol part of an URL (the part before `://`) is used to identify what VCS to use; URLs starting with `svn+` are handled by Subversion, while those starting with `git+` refer to git repositories. Additionally, URLs starting with `gitlab+` are used to download artifacts from [GitLab CI pipelines](https://docs.gitlab.com/ee/ci/pipelines/) or from the [Generic Packages Registry](https://docs.gitlab.com/ee/user/packages/generic_packages/).

#### Subversion ####

    # trunk of the library
    svn+ssh://svn.example.com/svn/blurlib/trunk
    # trunk at a particular revision
    svn+ssh://svn.example.com/svn/blurlib/trunk@92642
    # some branch of the library
    svn+ssh://svn.example.com/svn/blurlib/branches/fix-blurriness

Subversion URLs are the easiest; tags and branches are just regular subdirectories of a Subversion repository, and the "peg-revision" `@` syntax is used for the required revision. If a revision is not specified, the current HEAD is implied.

When updating an already checked-out dependency, `svn up` is used whenever possible, `svn switch` when necessary (`svn switch` _is_ able to do all that `svn up` can, but often touches files timestamps for no good reason).

Notice that this means that untracked files and whatever other garbage is left there by you or by svn is left untouched - no effort is made by Quark to clobber the dependency directory. This is deliberate, as a "clean", CI-made build should be made checking out everything from scratch anyway, while for development we don't want to risk removing user-made work (even if temporary).

#### Git ####

    # HEAD of the library
    git+ssh://git@git.example.com/widgets-inc/widgets.git
    # specific commit
    git+ssh://git@git.example.com/widgets-inc/widgets.git#commit=541acef52
    # specific branch
    git+ssh://git@git.example.com/widgets-inc/widgets.git#branch=fix-broken-comboboxes
    # specific tag
    git+ssh://git@git.example.com/widgets-inc/widgets.git#tag=r1.25

In Git URLs are generally used only to represent remotes, so some extra syntax has to be used to specify exactly what ref is to be extracted; the source of inspiration here are [sources for Arch Linux PKGBUILD files](https://wiki.archlinux.org/index.php/VCS_package_guidelines#VCS_sources), so `commit`, `branch` and `tag` fragments can be specified.

The update process for a git repository is essentially a `git fetch` + `git checkout`. As the specified refs are always relative to the remote, after Quark does his thing (checking out e.g. `origin/master`) the repository will be in detached head state; as this is often inconvenient, it's in the plans to add some heuristic to check out the corresponding local tracking branch, if available.

#### GitLab Artifacts from Generic Package Registry ####

NOTE: For this to work you need to set the `QUARK_GITLAB_PRIVATE_TOKEN` environment variable to a
[GitLab Personal Access Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
with the `read_api` scope.

    # Download a single binary
    gitlab+package://gitlab.example.com/widgets-inc/widgets/widgets-demo/1.0.0/demo.exe
    # Download a single binary, with expected SHA1 hash
    gitlab+package://gitlab.example.com/widgets-inc/widgets/widgets-demo/1.0.0/demo.exe#sha1=da39a3ee5e6b4b0d3255bfef95601890afd80709
    # Extract an archive (.tar.gz, .tar.bz2, .tar.xz, and .zip are supported)
    gitlab+package://gitlab.example.com/widgets-inc/widgets/widgets-package/1.0.0/package.tar.gz#extract=true
    # Extract an archive, with expected SHA1 hash of the archive itself
    gitlab+package://gitlab.example.com/widgets-inc/widgets/widgets-package/1.0.0/package.tar.gz#extract=true&sha1=da39a3ee5e6b4b0d3255bfef95601890afd80709

The URL format is:

    gitlab+package://<gitlab host>/<project path>/<package name>/<package version>/<package asset to download>

#### GitLab Artifacts from CI pipelines ####

NOTE: For this to work you need to set the `QUARK_GITLAB_PRIVATE_TOKEN` environment variable to a
[GitLab Personal Access Token](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
with the `read_api` scope.

    # Download an artifact from the given job on the latest successful pipeline on the given ref
    gitlab+ci://gitlab.example.com/widgets-inc/widgets/artifacts/path/to/file/in/artifacts/widgets.dll#ref=1.0.0&job=build-win32
    # Extract an archive from the given job on the latest successful pipeline on the given ref (.tar.gz, .tar.bz2, .tar.xz, and .zip are supported)
    gitlab+ci://gitlab.example.com/widgets-inc/widgets/artifacts/path/to/file/in/artifacts/widgets.tar.gz#ref=1.0.0&job=build-win32&extract=true
    # Extract an archive from the given job on the latest successful pipeline on the given ref, with expected SHA1 hash of the archive itself
    gitlab+ci://gitlab.example.com/widgets-inc/widgets/artifacts/path/to/file/in/artifacts/widgets.tar.gz#ref=1.0.0&job=build-win32&extract=true&sha1=da39a3ee5e6b4b0d3255bfef95601890afd80709
    # Download an artifact from the given job id
    gitlab+ci://gitlab.example.com/widgets-inc/widgets/artifacts/path/to/file/in/artifacts/widgets.dll#job=1234
    # Download an artifact from the given job id, with expected SHA1 hash
    gitlab+ci://gitlab.example.com/widgets-inc/widgets/artifacts/path/to/file/in/artifacts/widgets.dll#job=1234&sha1=da39a3ee5e6b4b0d3255bfef95601890afd80709
    # Extract an archive from the given job id, with expected SHA1 hash of the archive itself
    gitlab+ci://gitlab.example.com/widgets-inc/widgets/artifacts/path/to/file/in/artifacts/widgets.tar.gz#job=1234&extract=true&sha1=da39a3ee5e6b4b0d3255bfef95601890afd80709

The URL format is:

    gitlab+ci://<gitlab host>/<project path>/artifacts/<artifact's path>

### Options and optional dependencies ###

When specifying a dependency, it is possible to pass *options* to it; these are used essentially in two ways:

- to be automatically passed to the build system of the module (currently, only for CMake);
- to control *optional dependencies* of subprojects.

Let's get back to our *blur-app* example; *blurlib* may provide several blur algorithms, some of which may require arbitrary precision arithmetic; on the other hand, when compiling for weak ARM targets we just want the baseline stuff, to avoid wasting time with a library that we won't use and may not even be available for this architecture. We can specify it as an *optional dependency*:

```
{
    "description": "blurlib subprojects.quark",
    "depends": [
        "imagelib": { "url": "svn+ssh://svn.example.com/svn/imagelib/trunk" },
        "mathlib":  { "url": "svn+ssh://svn.another.example.com/svn/mathlib/trunk" }
    ],
    "optdepends": {
        "BLURLIB_ENABLE_LUXURY_BLURS": [{
            "value": true,
            "depends": {
                "aparith": { "url": "git+ssh://git@git.example.com/vendor/aparith.git#tag=v2.0" }
            }
        }]
    ]
}
```

As *blur-app* is an application for the true blur connoisseur, this feature is promptly enabled:

```
{
    "description": "blur-app subprojects.quark",
    "depends": [
        "blurlib": {
            "options": { "BLURLIB_ENABLE_LUXURY_BLURS": true },
            "url": "svn+ssh://svn.example.com/svn/blurlib/trunk"
        },
        "widgetslib": { "url": "git+ssh://git@git.example.com/widgets-inc/widgets.git" },
        "imagelib":   { "url": "svn+ssh://svn.example.com/svn/imagelib/trunk" }
    ]
}
```

This will have the effect of including `aparith` in the project dependencies, and of defining the CMake variable `BLURLIB_ENABLE_LUXURY_BLURS` in the `CMakeLists.txt` generated by Quark (more on this later).

#### `optdepends` structure ####

The general structure for `optdepends` is

```
{
    "optdepends": {
        "OPTION1": [ condition1, condition2, condition3, ...  ],
        "OPTION2": [ condition4, condition5, condition6, ...  ]
    }
}
```

where each `condition` is of the form

```
{
    "value": value_to_match,
    "depends": { dependencies as in the regular "depends" block }
}
```

When processing the module, the value of each `OPTION` is considered, and is compared to the `value` of the various conditions; conditions that match have their `depends` section processed, essentially as if it was contained in the regular `depends` section of the root object.

> Note: even though the data is stored in JSON files, comparison is performed using Python's `==` operator, so if you wanted to match `0` with `[null]` you are in for a sad surprise.

#### Adding options to existing modules ####

A `depends` block inside an option condition can also refer to an already referenced module, without repeating its URL, just to add another option to it; *blurlib* may also want to enable some extra stuff in *mathlib* if `BLURLIB_ENABLE_LUXURY_BLURS` is enabled; this is easily done:

```
{
    "description": "blurlib subprojects.quark",
    "depends": [
        "imagelib":  { "url": "svn+ssh://svn.example.com/svn/imagelib/trunk" },
        "mathlib":   { "url": "svn+ssh://svn.another.example.com/svn/mathlib/trunk" }
    ],
    "optdepends": {
        "BLURLIB_ENABLE_LUXURY_BLURS": [{
            "value": true,
            "depends": {
                "aparith": { "url": "git+ssh://git@git.example.com/vendor/aparith.git#tag=v2.0" },
                "mathlib": { "options": { "MATHLIB_EXTRA_POWERFUL_MATH": true } }
            }
        }]
    ]
}
```

#### Combining options, conflicts, acceptable values ####

When multiple projects depend from the same project, the options are combined:

- as long as they are independent, they are added to the options dictionary;
- if there are conflicting values for the same option, the process is aborted.

Thus, the general idea is for projects to provide **options that are _additive_ and compatible with each other**; this ensures that a dependency that enables some option doesn't break other projects that don't explicitly mention it.

Acceptable values for options are essentially JSON scalars, so booleans, numbers and strings; there is almost nothing _inside Quark_ that stops you from using lists and objects, but it's entirely unsupported, and will probably break when writing the `CMakeLists.txt`. _In practice_, there are probably zero places where in our code bases anything but boolean options are used.

#### Options scoping and naming ####

Scoping for options _started out_ as local for each dependency, but that quickly turned out to be just wishful thinking, especially as ultimately all options are lumped together when writing `CMakeLists.txt`; thus, **options scoping is now essentially _global_** (unfortunately it's a bit more complicated than this, but sooner or later it will be fixed).

This means that, as a module writer, you are expected to come up with options names that are unlikely to collide with options of other modules; prefixing them the name of the project is common accepted practice.

As these options get turned into CMake variables, they are generally spelled in [`SCREAMING_SNAKE_CASE`](https://en.wikipedia.org/wiki/Naming_convention_(programming)#Delimiter-separated_words) (i.e. like C preprocessor macros). Also for this reason, while Quark _per se_ shouldn't have any problem dealing with full-zalgo variable names, you should keep in mind that ultimately they will be fed to CMake, which is way more picky and guarantees hours of debugging fun whenever something goes wrong.

### Top-level checkout options ###

"Library-like" projects can often be checked out in two ways: as dependencies of another project, and as a standalone project, generally to develop the library and launch automatic tests.

If your library project has options, how would you set their when it is checked out as a top-level project?

The quick & dirty way is to use the `-o` argument to `quark up`; it allows you to specify the checkout options with `-o KEY=VALUE` syntax.

An approach that is usually more convenient is instead to use the `toplevel_options` field of the root object, which is a plain `"OPTION_NAME": "option_value"` dictionary (exactly as the `options` field in a dependency object).

For a library with optional dependencies, generally this means enabling all of them to have them checked out to test the full feature set. Testing the reduced feature set instead can be done (for CMake-based projects) by explicitly disabling the options through CMake when preparing the out-of-tree build.

Another case in which `toplevel_options` comes in handy is when your tests depend from a big data files, that you don't want to inflict on your dependent projects, that are generally uninterested in the tests; in this case, you can put the data files in a separate repository, have it as an optional dependency and enable the corresponding option only in `toplevel_options`.

To come back to our *blurlib* example, it would then become:

```
{
    "description": "blurlib subprojects.quark",
    "toplevel_options": { "BLURBLIB_ENABLE_LUXURY_BLURS": true, "BLURLIB_ENABLE_TEST_DATA": true },
    "depends": [
        "imagelib": { "url": "svn+ssh://svn.example.com/svn/imagelib/trunk" },
        "mathlib":  { "url": "svn+ssh://svn.another.example.com/svn/mathlib/trunk" }
    ],
    "optdepends": {
        "BLURLIB_ENABLE_LUXURY_BLURS": [{
            "value": true,
            "depends": {
                "aparith": { "url": "git+ssh://git@git.example.com/vendor/aparith.git#tag=v2.0" },
                "mathlib": { "options": { "MATHLIB_EXTRA_POWERFUL_MATH": true } }
            }
        }],
        "BLURLIB_ENABLE_TEST_DATA": [{
            "value": true,
            "depends": {
                "blurlib_test_data": { "url": "svn+ssh://svn.example.com/svn/blurlib_test_data/trunk" },
            }
        }]
    ]
}
```

## Advanced dependencies features ##

TODO

## CMake integration ##

TODO

## The catalog ##

As you start using Quark for many projects, the widespread duplication of the shared dependencies' URLs becomes problematic, as:

- it is tedious to keep copy-pasting stuff to setup new projects;
- it is also error-prone, as you may inadvertently start calling the same dependency with different names;
- it makes migrations of dependencies to "new homes" (be them just a different URL for the same data, or even Subversion to git migrations) more difficult, as all projects have to be manually updated.

For this reason, Quark supports a "catalog". Each `subprojects.quark` can specify a `catalog` entry consisting of an HTTP(S) URL from where the catalog is fetched.

The catalog file itself is structured in the same way as a `depends` section of a regular `subprojects.quark`, so it consists of an object mapping projects names to dependency objects, generally containing just the `url` entry, but that can also contain default options for the module.

When a `subprojects.quark` refers to a catalog, the content of the catalog is fetched; then, whenever a dependency is considered, the corresponding entry (if any) in the catalog is used as "starting point", and it is updated (as in Python's `dict.update`) with the `subprojects.quark`-specified data. This means that the project-specific data will always have the last word, but in general you can benefit from catalog-provided defaults, especially for the location.

In common usage this means that _generally_ most dependency entries in a `subprojects.quark` using a catalog will be empty objects (or at most containing just options), as the URL will be provided by the catalog. Our *blur-app* example using a catalog such as:

```
{
    "blurlib":    { "url": "svn+ssh://svn.example.com/svn/blurlib/trunk" },
    "widgetslib": { "url": "git+ssh://git@git.example.com/widgets-inc/widgets.git" },
    "imagelib":   { "url": "svn+ssh://svn.example.com/svn/imagelib/trunk" },
    "mathlib":    { "url": "svn+ssh://svn.another.example.com/svn/mathlib/trunk" }
    "aparith":    { "url": "git+ssh://git@git.example.com/vendor/aparith.git#tag=v2.0" }
}
```

will become something like

```
{
    "description": "blur-app subprojects.quark",
    "catalog": "https://catalog.example.com/quark-catalog.json",
    "depends": [
        "blurlib":    { "options": { "BLURLIB_ENABLE_LUXURY_BLURS": true } },
        "widgetslib": { },
        "imagelib":   { }
    ]
}
```

```
{
    "description": "blurlib subprojects.quark",
    "toplevel_options": { "BLURBLIB_ENABLE_LUXURY_BLURS": true, "BLURLIB_ENABLE_TEST_DATA": true },
    "depends": [
        "imagelib":  { },
        "mathlib":   { }
    ],
    "optdepends": {
        "BLURLIB_ENABLE_LUXURY_BLURS": [{
            "value": true,
            "depends": {
                "aparith": { },
                "mathlib": { }
            }
        }],
        "BLURLIB_ENABLE_TEST_DATA": [{
            "value": true,
            "depends": {
                "blurlib_test_data": { "url": "svn+ssh://svn.example.com/svn/blurlib_test_data/trunk" },
            }
        }]
    ]
}
```

### SSL issues ###

Python has a somewhat troubled relationship with certificates stores; at the moment of writing there are serious bugs related to Python being unable to find or use the system certificate store, in particular [on macOS](https://stackoverflow.com/a/42107877/214671) and [on every Windows version after Vista](https://stackoverflow.com/q/52074590/214671). For this reason, if your catalog is served through HTTPS you may be unable to access it due to certificate errors.

As a workaround, if certificate validation fails Quark tries to automatically fallback to using `curl` if it is in the `PATH`; this generally works well enough on macOS. In future we may try to fallback even on the `certifi` package, if it is installed, although it's suboptimal as well, as most often it will be outdated.

## Frozen dependencies (`freeze.quark`) ##

TODO

<!--

# THIS STUFF IS FOR A LATER CHAPTER #


our C++ *widgetslib* provides its `WImage` type, while *imagelib* provides its own `IImage`. As *widgetslib* is often used with *imagelib*, the latter can also provide efficient conversion routines between the two types, although they aren't compiled by default, as *imagelib* is also often used in project that don't use *widgetslib*.

Enter optional dependencies; the `subprojects.quark` of *imagelib* may look like this:

```
{
    "description": "imagelib subprojects.quark",
    "optdepends": {
        "IMAGELIB_WIDGETSLIB_SUPPORT": [{
            "value": true,
            "depends": {
                "widgetslib": { "url": "git+ssh://git@git.example.com/widgets-inc/widgets.git" }
            }
        }]
    }
}
```

in turn, the top-level *blur-app* project can enable the *imagelib* option in the `"options"` field of the dependency object:

```
{
    "description": "blur-app subprojects.quark",
    "depends": [
        "blurlib":    { "url": "svn+ssh://svn.example.com/svn/blurlib/trunk" },
        "widgetslib": { "url": "git+ssh://git@git.example.com/widgets-inc/widgets.git" },
        "imagelib": {
            "options": {
                "IMAGELIB_WIDGETSLIB_SUPPORT": true
            },
            "url": "svn+ssh://svn.example.com/svn/imagelib/trunk"
        }
    ]
}
```

-->
