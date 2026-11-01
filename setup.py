from setuptools import setup, find_packages

setup(
    name="ohmic",
    version="1.0.0",
    description="Ohmic Autonomous AI EDA & KiCad Schematic Toolsuite",
    author="Ohmic Engineering Team",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "ohmic": [".symbol_index.json", "*.json"],
    },
    entry_points={
        "console_scripts": [
            "ohmic=ohmic.cli:main",
        ],
    },
    python_requires=">=3.9",
)
