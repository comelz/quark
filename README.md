# Quark

Quark is a simple project dependency management that works at source code level.

## Commands

```
usage: quark-co [-h] [-v] [-o OPTIONS] [URL] [SOURCE_DIR]

Download a project source tree with all dependencies

positional arguments:
  URL                   Specify the checkout URL directory
  SOURCE_DIR            Specify the source directory

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Print dependency tree in JSON format
  -o OPTIONS, --options OPTIONS
                        set option value (will be taken into account when
                        downloading optional dependencies)

```
```
usage: quark-fz [-h] [SOURCE_DIR]

Freeze a project dependencies

positional arguments:
  SOURCE_DIR  Specify the source directory
```
```
usage: quark-st [-h] [SOURCE_DIR]

Check a project status

positional arguments:
  SOURCE_DIR  Specify the source directory
```
```
usage: quark-up [-h] [-v] [-o OPTIONS] [-d] [SOURCE_DIR]

Update all dependencies in a project source tree

positional arguments:
  SOURCE_DIR            Specify the source directory

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Print dependency tree in JSON format
  -o OPTIONS, --options OPTIONS
                        set option value (will be taken into account when
                        downloading optional dependencies)
  -d, --deps-only       Update only dependencies, ignore the root project
```

## Config files

Each package in `quark` can list it's own dependency in a `subprojects.quark` file:

```json
{
  "catalog": "https://https://github.com/comelz/some-catalog/master/catalog.json",
  "depends": {
    "cmake_commons" : { },
    "sipdir": { }
  },
  "optdepends": {
    "QT_SUPPORT": [
      {
        "value": true,
        "depends": {
          "qt-scripts" : { }
        }
      }
    ]
  }
}
```

Executing `quark up` the dependencies are cloned (`quark` supports `git` and `svn` sources) into the `lib/` folder.

```
some-project/
 |-- subprojects.quark
 \-- lib/
      |- cmake_commons/
      \- sipdir/
```
If `sipdir` package depends itself on `cmake_commons`, only a single copy is cloned, because `subprojects`
are supposed to be at same level in a parent project.

The `quark freeze` command generates the flattened resolved set of direct and indirect dependencies, and if found, the lock
file is used instead of exploring the dependency tree.

The real source paths are stored in a single `catalog.json` file, that is shaped like this:

```json
{
    "cmake_commons" :{
        "url":"svn+ssh://some-svn-server.com/packages/cmake_commons/trunk",
        "exclude_from_cmake" : true
    },
    "qt-scripts" : {
        "url": "git@github.com:some-qt-group/qt-scripts.git",
        "options": {
            "QT_SCRIPTS_QT5" : true
        }
    },
    ...
}
```

One can use `quark` without any catalog, adding the `"url"` entry in the `subprojects.quark` file directly
in each `"depends"`.
