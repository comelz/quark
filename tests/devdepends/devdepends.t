# Setup few testing env variables
  $ CRAMPTESTDIR=$PWD
  $ REPOS=$CRAMPTESTDIR/repos
  $ _QUARK=$TESTDIR/../../bin/quark

# Copy all the test directories
  $ mkdir repos && cd repos && cp -r $TESTDIR/cram_dir/test_dir_* ./

# Edit all urls in subprojects
  $ cd test_dir_1 &&
  > sed -i -e "s|PH_TESTDIR2|$REPOS/test_dir_2|g" subprojects.quark &&
  > cd ..
  $ cd test_dir_2 &&
  > sed -i -e "s|PH_TESTDIR3|$REPOS/test_dir_3|g" subprojects.quark &&
  > sed -i -e "s|PH_TESTDIR4|$REPOS/test_dir_4|g" subprojects.quark &&
  > cd ..

# Setup the fake git repos
  $ cd test_dir_1 && git -c init.defaultBranch=initial init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..
  $ cd test_dir_2 && git -c init.defaultBranch=initial init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..
  $ cd test_dir_3 && git -c init.defaultBranch=initial init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..
  $ cd test_dir_4 && git -c init.defaultBranch=initial init > /dev/null && git add * && git commit -m "1st commit" > /dev/null && cd ..

# Clone the root testing git repo
  $ cd $CRAMPTESTDIR
  $ mkdir checkout && cd checkout
  $ git clone file://$REPOS/test_dir_1 > /dev/null 2>&1

# Quark UP from the root
  $ cd test_dir_1
  $ $_QUARK up > /dev/null 2>&1

# Check that we have downloaded the expected dependencies
  $ test -d lib/test_dir_2
  $ test -d lib/test_dir_4
  $ test ! -d lib/test_dir_3
