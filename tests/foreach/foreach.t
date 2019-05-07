SETUP PYTHON

$ [ -n "$PYTHON" ] || PYTHON="`which python`"
$ [ -n "$PYTHONPATH" ] || PYTHONPATH="$TESTDIR/.." && export PYTHONPATH

TEST FOREACH

  $ cp -r $TESTDIR/test_dir_1 test_dir_1
  $ cd test_dir_1
  $ git remote add origin file://$TESTDIR/test_dir_1
  $ cd src/test_dir_2
  $ git remote add origin file://$TESTDIR/test_dir_1/src/test_dir_2
  $ cd ../..
  $ cd src/test_dir_3
  $ git remote add origin file://$TESTDIR/test_dir_1/src/test_dir_3
  $ cd ../..
  $ quark freeze > /dev/null
  $ quark foreach 'echo $name $sm_path $displaypath $sha1 $toplevel $rev $version_control'
  .* (re)
  .* (re)
  test_dir_2 src/test_dir_2 src/test_dir_2 b65618e80ec59a34b1178b148410d358263e9123 /tmp/cramtests-.*/foreach.t/test_dir_1 git (re)
   (re)
  test_dir_3 src/test_dir_3 src/test_dir_3 f7e94048b2b2d5a3987ec00ed048fc3fac7a74f0 /tmp/cramtests-.*/foreach.t/test_dir_1 git (re)
   (re)


HELPER
  $ python $TESTDIR/../../bin/quark foreach --help
  usage: quark foreach [-h] [-q] command [command ...]
   (re)
  Evaluates an arbitrary shell command in each submodule, skipping all the svn's
  submodules. The command has access to the variables $name, $sm_path,
  $displaypath, $sha1, $toplevel, $rev, $version_control: $name is the name of
  the submodule; $sm_path is the path of the submodule relative to the
  superproject; $displaypath is the path of the submodule relative to the root
  directory; $version_control is the version control used by the subproject
  (git/svn); $sha1 is the commit of the subproject ( empty string if it is a svn
  repository ); $rev is the revision of the subproject ( empty string if it is a
  git repository ); $toplevel is the absolute path to the top-level of the
  immediate superproject.
   (re)
  positional arguments:
    command      The command that will be run for every dependency
   (re)
  optional arguments:
    -h, --help   show this help message and exit
    -q, --quiet  Only print error messages
