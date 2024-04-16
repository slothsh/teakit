#!/usr/bin/env python3

from setuptools import setup
import tomllib

CONFIG = tomllib.load(open("./project.toml", "rb"))
PROJECT_NAME = CONFIG["name"]
PROJECT_AUTHOR = CONFIG["author"]
PROJECT_URL = CONFIG["url"]
PROJECT_DESCRIPTION = CONFIG["description"]
AUTHOR_EMAIL = CONFIG["email"]

VERSION = f"{CONFIG['version']['major']}.{CONFIG['version']['minor']}.{CONFIG['version']['sub']}"

# Setup Entry Point
# --------------------------------------------------------------------------------

if __name__ == "__main__":
    setup(
        name=PROJECT_NAME,
        author=PROJECT_AUTHOR,
        author_email=AUTHOR_EMAIL,
        description=PROJECT_DESCRIPTION,
        version=VERSION,
        url=PROJECT_URL,
        packages=["teakit"],
        package_dir={
            "teakit": "src",
        },
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        python_requires='>=3.6',
        install_requires=[
            "termcolor >= 2.4.0",
            "dill >= 0.3.8",
        ],
    )

# --------------------------------------------------------------------------------
