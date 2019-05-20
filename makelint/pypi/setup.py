import io
from setuptools import setup

GITHUB_URL = "https://github.com/cheshirekow/makelint"

VERSION = None
with io.open("makelint/__init__.py", encoding="utf-8") as infile:
  for line in infile:
    line = line.strip()
    if line.startswith("VERSION ="):
      VERSION = line.split("=", 1)[1].strip().strip('"')

assert VERSION is not None
with io.open("README.rst", encoding="utf-8") as infile:
  long_description = infile.read()

setup(
    name="makelint",
    packages=["makelint"],
    version=VERSION,
    description=(
        "A highly-compatible \"build\" system for linting python files."),
    long_description=long_description,
    author="Josh Bialkowski",
    author_email="josh.bialkowski@gmail.com",
    url=GITHUB_URL,
    download_url="{}/archive/{}.tar.gz".format(GITHUB_URL, VERSION),
    keywords=["lint", "static-analysis", "code-checker"],
    classifiers=[],
    entry_points={
        "console_scripts": [
            "pymakelint=makelint.__main__:main",
        ],
    },
    extras_require={},
    install_requires=[]
)
