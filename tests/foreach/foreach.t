# Setup few testing env variables
  $ CRAMPTESTDIR=$PWD
  $ REPOS=$CRAMPTESTDIR/repos

# Copy all the test directories
  $ mkdir repos && cd repos && cp -r $TESTDIR/cram_dir/test_dir_* ./

# Edit all urls in subprojects
  $ cd test_dir_1 &&
  > sed -i -e "s|PH_TESTDIR2|$REPOS/test_dir_2|g" subprojects.quark &&
  > sed -i -e "s|PH_TESTDIR3|$REPOS/test_dir_3|g" subprojects.quark &&
  > cd ..
  $ cd test_dir_2 &&
  > sed -i -e "s|PH_TESTDIR4|$REPOS/test_dir_4|g" subprojects.quark &&
  > cd ..

# Setup the fake git repos
  $ cd test_dir_1 && git init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..
  $ cd test_dir_2 && git init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..
  $ cd test_dir_3 && git init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..
  $ cd test_dir_4 && git init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..

# Clone the root testing git repo
  $ cd $CRAMPTESTDIR
  $ mkdir checkout && cd checkout
  $ git clone file://$REPOS/test_dir_1 > /dev/null
  Cloning into 'test_dir_1'...

# Quark UP from the root and setup a new variable ROOT_TEST
  $ cd test_dir_1
  $ ROOT_TEST=$CRAMPTESTDIR/checkout/test_dir_1
  $ quark up >/dev/null 2>&1

# Test foreach's output with a simple echo of its env variables
  $ quark foreach 'echo $name $sm_path $displaypath $sha1 $toplevel $rev $version_control'
  .* (re)
  .* (re)
  Entering test_dir_2
  test_dir_2 src/test_dir_2 src/test_dir_2 .+ /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 git (re)
  Entering test_dir_3
  test_dir_3 src/test_dir_3 src/test_dir_3 .+ /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 git (re)
  Entering test_dir_4
  test_dir_4 src/test_dir_4 src/test_dir_4 .+ /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 git (re)

# Test foreach with a shell script
  $ quark foreach $TESTDIR/foreach.sh
  .* (re)
  .* (re)
  Entering test_dir_2
  name: test_dir_2
  sm_path: src/test_dir_2
  displaypath: src/test_dir_2
  version_control: git
  sha1: .+ (re)
  rev:\s* (re)
  toplevel: /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 (re)
  Entering test_dir_3
  name: test_dir_3
  sm_path: src/test_dir_3
  displaypath: src/test_dir_3
  version_control: git
  sha1: .+ (re)
  rev:\s* (re)
  toplevel: /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 (re)
  Entering test_dir_4
  name: test_dir_4
  sm_path: src/test_dir_4
  displaypath: src/test_dir_4
  version_control: git
  sha1: .+ (re)
  rev:\s* (re)
  toplevel: /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 (re)

# Freeze the dependencies
  $ cd $ROOT_TEST
  $ quark freeze > /dev/null

# Repeat the first test with the frozen version
# This time I wanna be sure that the given commits are SHA-1 hashes
# The check for the hashes is done by the regex '[a-fA-F0-9]{40}'
# (Match exactly 40 times any word character)
  $ quark foreach 'echo $name $sm_path $displaypath $sha1 $toplevel $rev $version_control'
  .* (re)
  .* (re)
  Entering test_dir_2
  test_dir_2 src/test_dir_2 src/test_dir_2 [a-fA-F0-9]{40} /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 git (re)
  Entering test_dir_3
  test_dir_3 src/test_dir_3 src/test_dir_3 [a-fA-F0-9]{40} /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 git (re)
  Entering test_dir_4
  test_dir_4 src/test_dir_4 src/test_dir_4 [a-fA-F0-9]{40} /tmp/cramtests-.*/foreach.t/checkout/test_dir_1 git (re)
