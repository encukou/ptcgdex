from setuptools import setup, find_packages
setup(
    name = 'TCGdex',
    version = '0.1',
    zip_safe = False,
    packages = find_packages(),
    package_data = {
        'pokedex': ['data/csv/*.csv']
    },
    install_requires=[
        'pokedex',
        'pyyaml',
        'docopt',
    ],

    entry_points = {
        'console_scripts': [
            'ptcgdex = ptcgdex.main:main',
        ],
    },
)
