from os.path import join, dirname
from setuptools import setup
from quark.entrypoints import mk_setup_entry_points

config = {
    'name': "quark",
    'version': "0.6",
    'author': "Comelz SpA",
    'author_email': "software@comelz.com",
    'description': ("Dependency management plugin"),
    'long_description': '',
    'license': "MIT",
    'keywords': "build",
    'url': "https://github.com/comelz/quark",
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
        'console_scripts': mk_setup_entry_points()
    }
}

if __name__ == "__main__":
    setup(**config)
