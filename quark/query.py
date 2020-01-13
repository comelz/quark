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
        help="The attribute to query. At the moment only subprojects-dir is supported"
    )
    parser.add_argument(
        "--abspath",
        action="store_true",
        help="For path attributes print the absolute path."
    )

    args = parser.parse_args()
    source_dir = os.path.join(os.path.abspath("."), '')
    conf = load_conf(source_dir)
    if conf is None:
        print("This is not a quark project. Aborting.")
        sys.exit(1)
    attr = args.attribute
    if attr == "subprojects_dir":
        subprojects_dir = conf.get("subprojects_dir", 'lib')
        if args.abspath:
            print(os.path.join(source_dir, subprojects_dir))
        else:
            print(subprojects_dir)
    else:
        print("Unsupported attribute '%s'." % attr)
        sys.exit(1)

if __name__ == "__main__":
    run()
