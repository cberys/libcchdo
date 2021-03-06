from __future__ import with_statement
from setuptools import setup, find_packages
import sys
import os

import libcchdo
from libcchdo.setup_commands import (
    DIRECTORY, PACKAGE_NAME,
    CoverageCommand, CleanCommand, PurgeCommand, ProfileCommand, REPLCommand,
    )


if __name__ == "__main__":
    long_description = ''
    try:
        with open(os.path.join(DIRECTORY, 'README.txt')) as f:
            long_description = f.read()
    except IOError:
        pass

    # To install extras with pip as editable:
    # pip install -e .[all] will install all extras
    # pip install -e .[db,speed,netcdf]
    extras_require = {
        'csv_view': ['lxml', ],
        'kml': ['pykml', ],
        'coverage': ['coverage', ],
        'netcdf': ['numpy', 'netCDF4', ],
        'autocomplete': ['argcomplete'],
        'merge': ['numpy>=1.6'],
        #'plot': ['numpy>=1.4', 'scipy', 'pillow', 'matplotlib', 'basemap', ],
        'dap_thredds': ['lxml', 'httplib2', 'pydap'],
    }
    extras_require['all'] = extras_require.values()

    install_requires = [
        'mpmath',
        'SQLalchemy',
        'zope.sqlalchemy',
    ]
    if sys.version_info[:3] < (2,5,0):
        install_requires.append('pysqlite')
    if sys.version_info[:3] < (2,7,0):
        install_requires.append('argparse')

    packages = find_packages(exclude=['libcchdo.tests'])

    resources = []
    resources_path = os.path.join(PACKAGE_NAME, 'resources')
    for dirname, dirs, fnames in os.walk(resources_path):
        dirname = dirname.replace(PACKAGE_NAME + '/', '')
        for fname in fnames:
            resources.append(os.path.join(dirname, fname))

    setup(
        name=PACKAGE_NAME,
        version=libcchdo.__version__,
        description="CLIVAR and Carbon Hydrographic Data Office library",
        long_description=long_description,
        provides=[PACKAGE_NAME],
        packages=packages,
        package_data={PACKAGE_NAME:[
            'RELEASE-VERSION.txt',
            ] + resources,
        },
        test_suite='libcchdo.tests',
        install_requires=install_requires,
        extras_require=extras_require,
        entry_points={
            'console_scripts': [
                'hydro = libcchdo.scripts:main',
            ],
        },
        cmdclass={
            'coverage': CoverageCommand,
            'clean': CleanCommand,
            'purge': PurgeCommand,
            'profile': ProfileCommand,
            'repl': REPLCommand,
        },
    )
