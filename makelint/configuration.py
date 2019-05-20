from __future__ import unicode_literals

import inspect
import logging
import multiprocessing
import os
import re
import subprocess
import sys

logger = logging.getLogger()

REGEX_TYPE = type(re.compile(""))


def serialize(obj):
  """
  Return a serializable representation of the object. If the object has an
  `as_dict` method, then it will call and return the output of that method.
  Otherwise return the object itself.
  """
  if hasattr(obj, 'as_dict'):
    fun = getattr(obj, 'as_dict')
    if callable(fun):
      return fun()
  elif isinstance(obj, (list, tuple)):
    return type(obj)(serialize(x) for x in obj)
  elif isinstance(obj, dict):
    return {field: serialize(value)
            for field, value in obj.items()}
  elif isinstance(obj, REGEX_TYPE):
    return obj.pattern

  return obj


def parse_bool(string):
  """
  Evaluate the truthiness of a string
  """

  if string.lower() in ('y', 'yes', 't', 'true', '1', 'yup', 'yeah', 'yada'):
    return True
  if string.lower() in ('n', 'no', 'f', 'false', '0', 'nope', 'nah', 'nada'):
    return False

  logger.warning("Ambiguous truthiness of string '%s' evalutes to 'FALSE'",
                 string)
  return False


class ConfigObject(object):
  """
  Provides simple serialization to a dictionary based on the assumption that
  all args in the __init__() function are fields of this object.
  """

  @classmethod
  def get_field_names(cls):
    """
    Return a list of field names, extracted from kwargs to __init__().
    The order of fields in the tuple representation is the same as the order
    of the fields in the __init__ function
    """

    # NOTE(josh): args[0] is `self`
    if sys.version_info >= (3, 5, 0):
      sig = getattr(inspect, 'signature')(cls.__init__)
      return [field for field, _ in list(sig.parameters.items())[1:-1]]

    return getattr(inspect, 'getargspec')(cls.__init__).args[1:]

  def as_dict(self):
    """
    Return a dictionary mapping field names to their values only for fields
    specified in the constructor
    """
    return {field: serialize(getattr(self, field))
            for field in self.get_field_names()}


def get_default(value, default):
  """
  return ``value`` if it is not None, else default
  """
  if value is None:
    return default

  return value


class SimpleTool(object):
  """
  Simple implementation of the tool API that works for commands which
  just take the name of the file as an argument.
  """

  def __init__(self, name):
    self.name = name

  def as_dict(self):
    return self.name

  def get_stamp(self, target_cwd, filename):
    return os.path.join(target_cwd, filename + "." + self.name)

  def execute(self, source_tree, source_relpath, env, outfile):
    cmd = [self.name, source_relpath]
    if self.name == "pylint":
      cmd = [self.name, "--output-format=text", source_relpath]
    return subprocess.call(
        cmd, cwd=source_tree, env=env, stdout=outfile)


class Configuration(ConfigObject):
  """
  Encapsulates various configuration options/parameters
  """

  # pylint: disable=R0913
  def __init__(
      self,
      include_patterns=None,
      exclude_patterns=None,
      source_tree=None,
      target_tree=None,
      tools=None,
      env=None,
      fail_fast=False,
      merge_log=None,
      quiet=False,
      jobs=None,
      **extra):

    self.include_patterns = [
        re.compile(pattern) for pattern in
        get_default(include_patterns, [".*\\.py"])
    ]
    self.exclude_patterns = [
        re.compile(pattern) for pattern in
        get_default(exclude_patterns, [])
    ]
    self.source_tree = source_tree
    self.target_tree = get_default(target_tree, os.getcwd())
    self.tools = []
    for tool in get_default(tools, ["flake8", "pylint"]):
      if isinstance(tool, str):
        self.tools.append(SimpleTool(tool))
      else:
        self.tools.append(tool)
    self.env = get_default(env, os.environ.copy())
    self.fail_fast = fail_fast
    self.merge_log = merge_log
    self.quiet = quiet
    self.jobs = get_default(jobs, multiprocessing.cpu_count())

    extra_keys = []
    for key in extra:
      if key.startswith('_'):
        continue
      if inspect.ismodule(extra[key]):
        continue
      extra_keys.append(key)

    if extra_keys:
      logger.warning(
          "Unused config file options: %s", ", ".join(sorted(extra_keys))
      )

  def clone(self):
    """
    Return a copy of self.
    """
    return Configuration(**self.as_dict())


VARCHOICES = {}

VARDOCS = {
    "include_patterns": """
A list of python regular expression patterns which are used to include
files during the directory walk. They are matched against relative paths
of files (relative to the root of the search). They are not matched against
directories. The default is `[".*\\.py"]`.
""",
    "exclude_patterns": """
A list of python regular expression patterns which are used to exclude
files during the directory walk. They are matched against relative
paths of files (relative to the root of the search). If the pattern matches
a directory the whole directory is skipped. If it matches an individual file
then that file is skipped.
""",
    "source_tree": """
The root of the search tree for inclusion.
""",
    "target_tree": """
The root of the tree where the outputs are written.
""",
    "tools": """
A list of tools to execute. The default is ["pylint", "flake8"]. This can
either be a string (a simple command which takes one argument), or it can
be an object with a get_stamp() and an execute() method. See SimpleTool for
ane example.
""",
    "env": """
A dictionary specifying the environment to use for the tools. Add your
virtualenv configurations here.
""",
    "fail_fast": """
If true, exit on the first failure, don't keep going. Useful if you want a
speedy CI gate.
""",
    "merge_log": """
If specified, output logs for failed jobs will be merged into a single file
at this location. Useful if you have a large number of issues to del with.
""",
    "quiet": """
Don't print fancy progress bars to stdout.
""",
    "jobs": """
Number of parallel jobs to execute.
"""
}
