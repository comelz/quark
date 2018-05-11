from os.path import join, dirname
from setuptools import setup, find_packages


def read(fname):
    return open(join(dirname(__file__), fname)).read()


config = {
    'name': "quark",
    'version': "0.1",
    'author': "Walter Oggioni",
    'author_email': "oggioni.walter@gmail.com",
    'description': ("Meson dependency management plugin"),
    'long_description': '',
    'license': "MIT",
    'keywords': "build",
    'url': "https://github.com/comelz/czmake",
    'packages': ['quark'],
    'include_package_data': True,
    'classifiers': [
        'Development Status :: 3 - Alpha',
        'Topic :: Utilities',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: System Administrators',
        'Intended Audience :: Developers',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Topic :: Software Development :: Version Control',
        'Topic :: Utilities'
    ],
    "entry_points": {
        'console_scripts': [
            'quark=quark.cli:main',
            'quark-checkout=quark.checkout:checkout',
            'quark-co=quark.checkout:checkout',
            'quark-update=quark.checkout:update',
            'quark-up=quark.checkout:update',
            'quark-freeze=quark.freeze:freeze',
        ],
    }
}
setup(**config)
