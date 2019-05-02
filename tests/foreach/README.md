COMMAND LINE TESTING SCRIPTS:
```
..
  |
  |- foreach.py
  |- foreach.sh
```

HOW TO TEST BOTH SCRIPTS

Working directory must be in the root of a superproject with some subproject dependencies

To tests the scripts launch the following commands:

`python ../quark/bin/quark foreach '../quark/tests/foreach/foreach.sh'`
`python ../quark/bin/quark foreach '../quark/tests/foreach/foreach.py'`

The output should be a list of elements for every quark's submodule in the superproject.
Every print has 5 elements for each submodule and the output should be like this:
```
name: <name>
sm_path: <sm_path>
displaypath: <displaypath>
sha1: <sha1>
toplevel: <toplevel>

name: <name>
sm_path: <sm_path>
...
...
```
