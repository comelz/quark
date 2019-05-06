#! /usr/bin/env python
import os

print("name: {}".format(os.environ["name"]))
print("sm_path: {}".format(os.environ["sm_path"]))
print("displaypath: {}".format(os.environ["displaypath"]))
print("version_control: {}".format(os.environ["version_control"]))
try:
    print("sha1: {}".format(os.environ["sha1"]))
except KeyError:
    print("rev: {}".format(os.environ["rev"]))
print("toplevel: {}".format(os.environ["toplevel"]))
