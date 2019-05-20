# -*- coding: utf-8 -*-
"""
Incremental execution system for python code analysis (linting).
"""
from __future__ import unicode_literals

import argparse
import io
import json
import logging
import os
import pprint
import sys
import textwrap

import makelint
from makelint import configuration

logger = logging.getLogger()


def load_config(configfile_path):
  """
  Read a configuration file and return as a configuration object
  """
  config_dict = configuration.Configuration().as_dict()
  if configfile_path is None:
    return config_dict

  if os.path.exists(configfile_path):
    with io.open(configfile_path, 'r', encoding='utf-8') as infile:
      # pylint: disable=exec-used
      exec(infile.read(), config_dict)
  return config_dict


def dump_config(args, config_dict, outfile):
  """
  Dump the default configuration to stdout
  """

  for key, value in vars(args).items():
    if (key in configuration.Configuration.get_field_names()
        and value is not None):
      config_dict[key] = value

  cfg = configuration.Configuration(**config_dict)
  ppr = pprint.PrettyPrinter(indent=2)
  config_dict = cfg.as_dict()

  # strip some common cruft from the environment
  env = config_dict.get("env", {})
  for key, value in list(env.items()):
    if not key.endswith("PATH"):
      continue
    env[key] = value.split(os.pathsep)

  for key in configuration.Configuration.get_field_names():
    value = config_dict[key]
    helptext = configuration.VARDOCS.get(key, None)
    if helptext:
      for line in textwrap.wrap(helptext, 78):
        outfile.write('# ' + line.lstrip() + '\n')
    if key == "target_tree":
      value = None

    if key == "jobs":
      outfile.write(
          "{} = {}  # multiprocessing.cpu_count()\n\n"
          .format(key, ppr.pformat(value)))
    elif isinstance(value, dict):
      outfile.write(
          "{} = {}\n\n".format(
              key, json.dumps(value, indent=2, sort_keys=True)))
    else:
      outfile.write("{} = {}\n\n".format(key, ppr.pformat(value)))


def add_config_options(optgroup):
  """
  Add configuration options as flags to the argument parser
  """
  default_config = configuration.Configuration().as_dict()
  if sys.version_info[0] >= 3:
    value_types = (str, int, float)
  else:
    value_types = (str, unicode, int, float)

  for key in configuration.Configuration.get_field_names():
    value = default_config[key]
    helptext = configuration.VARDOCS.get(key, None)
    # NOTE(josh): argparse store_true isn't what we want here because we want
    # to distinguish between "not specified" = "default" and "specified"
    if key == 'additional_commands':
      continue
    elif isinstance(value, bool):
      optgroup.add_argument('--' + key.replace('_', '-'), nargs='?',
                            default=None, const=(not value),
                            type=configuration.parse_bool, help=helptext)
    elif isinstance(value, value_types):
      optgroup.add_argument('--' + key.replace('_', '-'), type=type(value),
                            help=helptext,
                            choices=configuration.VARCHOICES.get(key, None))
    elif value is None:
      # If the value is None then we can't really tell what it's supposed to
      # be. I guess let's assume string in this case.
      optgroup.add_argument('--' + key.replace('_', '-'), help=helptext,
                            choices=configuration.VARCHOICES.get(key, None))
    # NOTE(josh): argparse behavior is that if the flag is not specified on
    # the command line the value will be None, whereas if it's specified with
    # no arguments then the value will be an empty list. This exactly what we
    # want since we can ignore `None` values.
    elif isinstance(value, (list, tuple)):
      typearg = None
      if value:
        typearg = type(value[0])
      optgroup.add_argument('--' + key.replace('_', '-'), nargs='*',
                            type=typearg, help=helptext)


def setup_argparser(parser):
  """
  Add argparse options to the parser.
  """
  parser.add_argument('-v', '--version', action='version',
                      version=makelint.VERSION)

  parser.add_argument(
      "-l", "--log-level", default="warning",
      choices=["debug", "info", "warning", "error"])
  parser.add_argument(
      "--dump-config", action="store_true",
      help="If specified, print the default configuration to stdout and exit")
  parser.add_argument(
      '-c', '--config-file',
      help='path to configuration file')

  optgroup = parser.add_argument_group(
      title='Configuration',
      description='Override configfile options')
  add_config_options(optgroup)


USAGE_STRING = """
pymakelint [-h] [-v] [-l {debug,info,warning,error}] [--dump-config]
           [-c CONFIG_FILE] [<config-overrides> [...]]
"""


def main():
  """
  Parse arguments, open files, start work.
  """
  logging.basicConfig(level=logging.WARNING)
  arg_parser = argparse.ArgumentParser(
      description=__doc__, usage=USAGE_STRING)
  setup_argparser(arg_parser)
  args = arg_parser.parse_args()
  logger.setLevel(getattr(logging, args.log_level.upper()))

  config_path = args.config_file
  if config_path is None and args.source_tree is not None:
    try_config_path = os.path.join(args.source_tree, ".makelint.py")
    if os.path.exists(try_config_path):
      config_path = try_config_path

  config_dict = load_config(config_path)
  for key, value in vars(args).items():
    if (key in configuration.Configuration.get_field_names()
        and value is not None):
      config_dict[key] = value

  if args.dump_config:
    dump_config(args, config_dict, sys.stdout)
    sys.exit(0)

  cfg = configuration.Configuration(**config_dict)
  if cfg.quiet:
    progress = makelint.NullProgressReport()
  else:
    progress = makelint.ProgressReporter()

  progress(ntools=len(cfg.tools) + 2)
  makelint.discover_sourcetree(
      cfg.source_tree, cfg.target_tree,
      cfg.exclude_patterns, cfg.include_patterns, progress)
  makelint.digest_sourcetree_content(
      cfg.source_tree, cfg.target_tree, progress, cfg.jobs)
  makelint.map_sourcetree_dependencies(
      cfg.source_tree, cfg.target_tree, progress, cfg.jobs)

  merged_log = None
  if cfg.merge_log:
    merged_log = open(cfg.merge_log, "w", encoding="utf-8")

  retcode = 0
  for tool in cfg.tools:
    retcode |= makelint.execute_tool_ontree(
        cfg.source_tree, cfg.target_tree, tool, cfg.env,
        cfg.fail_fast, merged_log, progress, cfg.jobs)

  if merged_log:
    merged_log.close()

  progress(force=True, rewind=False)
  return retcode


if __name__ == '__main__':
  sys.exit(main())
