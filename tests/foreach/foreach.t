SETUP PYTHON

$ [ -n "$PYTHON" ] || PYTHON="`which python`"
$ [ -n "$PYTHONPATH" ] || PYTHONPATH="$TESTDIR/.." && export PYTHONPATH

SETUP TEST DIR
  $ cp -r $TESTDIR/cram_dir/test_dir_1 test_dir_1
  $ cd test_dir_1
  $ git init
  .* (re)
  $ git remote add origin file://$TESTDIR/cram_dir/test_dir_1
  $ git add *
  $ git commit -m "First Commit"
  .* (re)
  .* (re)
  .* (re)
  $ mkdir src
  $ cd src
  $ cp -r $TESTDIR/cram_dir/test_dir_2 test_dir_2
  $ cd test_dir_2
  $ git init
  .* (re)
  $ git remote add origin file://$TESTDIR/cram_dir/test_dir_2
  $ git add *
  $ git commit -m "First Commit"
  .* (re)
  .* (re)
  .* (re)
  $ cd ..
  $ cp -r $TESTDIR/cram_dir/test_dir_3 test_dir_3
  $ cd test_dir_3
  $ git init
  .* (re)
  $ git add *
  $ git commit -m "First Commit"
  .* (re)
  .* (re)
  .* (re)
  $ git remote add origin file://$TESTDIR/cram_dir/test_dir_3
  $ cd ..
  $ cp -r $TESTDIR/cram_dir/test_dir_4 test_dir_4
  $ cd test_dir_4
  $ git init
  .* (re)
  $ git add *
  $ git commit -m "First Commit"
  .* (re)
  .* (re)
  .* (re)
  $ git remote add origin file://$TESTDIR/cram_dir/test_dir_4
  $ cd ../..
  $ quark freeze > /dev/null

TEST FOREACH WITH COMMAND
  $ quark foreach 'echo $name $sm_path $displaypath $sha1 $toplevel $rev $version_control'
  .* (re)
  .* (re)
  test_dir_2 src/test_dir_2 src/test_dir_2 bbad4b8fc3c58b39e14956bc81d73b756a08160e /tmp/cramtests-.*/foreach.t/test_dir_1 git (re)
   (re)
  test_dir_3 src/test_dir_3 src/test_dir_3 f7e94048b2b2d5a3987ec00ed048fc3fac7a74f0 /tmp/cramtests-.*/foreach.t/test_dir_1 git (re)
   (re)
  test_dir_4 src/test_dir_4 src/test_dir_4 13a506afbbae847c8878c04f6f305dff597e3d7d /tmp/cramtests-.*/foreach.t/test_dir_1 git (re)
   (re)


TEST FOREACH WITH SCRIPT
  $ quark foreach $TESTDIR/foreach.sh
  .* (re)
  .* (re)
  name: test_dir_2
  sm_path: src/test_dir_2
  displaypath: src/test_dir_2
  version_control: git
  sha1: bbad4b8fc3c58b39e14956bc81d73b756a08160e
  rev: \w* (re)
  toplevel: /tmp/cramtests-.*/foreach.t/test_dir_1/test_dir_1 (re)
   (re)
  name: test_dir_3
  sm_path: src/test_dir_3
  displaypath: src/test_dir_3
  version_control: git
  sha1: f7e94048b2b2d5a3987ec00ed048fc3fac7a74f0
  rev: \w* (re)
  toplevel: /tmp/cramtests-.*/foreach.t/test_dir_1/test_dir_1 (re)
   (re)
  name: test_dir_4
  sm_path: src/test_dir_4
  displaypath: src/test_dir_4
  version_control: git
  sha1: 13a506afbbae847c8878c04f6f305dff597e3d7d
  rev: \w* (re)
  toplevel: /tmp/cramtests-.*/foreach.t/test_dir_1/test_dir_1 (re)
   (re)
