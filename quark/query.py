# -*- coding: utf-8 *--

from argparse import ArgumentParser
from quark.utils import load_conf
import sys
import os

def run():
    parser = ArgumentParser(
        description="""
        Query an attribute for the current project.
        Supported attributes:
        subprojects-dir : base directory where the dependencies will be extracted.
        """
    )
    parser.add_argument(
        "attribute",
        action="store",
        nargs=1,
        help="The attribute to query. At the moment only subprojects-dir is supported"
    )

    args = parser.parse_args()
    source_dir = os.path.join(os.path.abspath("."), '')
    conf = load_conf(source_dir)
    if conf is None:
        print("This is not a quark project. Aborting.")
        sys.exit(1)
    if len(args.attribute) != 1:
        print("Only one attribute can be queried.")
        sys.exit(1)
    attr = args.attribute[0]
    if attr == "subprojects_dir":
        print(os.path.join(source_dir, conf.get("subprojects_dir", 'lib')))
    else:
        print("Unsupported attribute '%s'." % attr)
        sys.exit(1)

if __name__ == "__main__":
    run()
