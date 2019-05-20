import os

include_patterns = [".*\\.py"]
exclude_patterns = [
  ".build",
  ".git",
  "third_party",
  ".*/conf.py",
  ".*__pycache__",
  "\\.[^/]+\\.py",
  ".*/\\.[^/]+\\.py"
]
tools = ["flake8", "pylint"]

_home = os.getenv("HOME")
env = {
  "LANG": "en_US.UTF-8",
  "LANGUAGE": "en_US",
  "PATH": ":".join([
    "{}/.pyenv/python3/bin".format(_home),
    "{}/.local/bin".format(_home),
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
  ]),
  "VIRTUAL_ENV": "{}/.pyenv/python3".format(_home),
}
