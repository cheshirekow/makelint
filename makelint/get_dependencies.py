"""
Helper module to get dependencies. exec() a python file and then inspect
``sys.modules`` and record everything that was read in.
"""

import argparse
import os
import sys


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-m", "--module-relpath", required=True)
  parser.add_argument("-s", "--source-tree", required=True)
  parser.add_argument("-t", "--target-tree", required=True)
  args = parser.parse_args()

  source_tree = os.path.realpath(args.source_tree)
  target_tree = os.path.realpath(args.target_tree)
  module_path = os.path.join(source_tree, args.module_relpath)
  target_path = os.path.join(target_tree, args.module_relpath)

  try:
    with open(module_path) as infile:
      # NOTE(josh): if we allow __name__ to pass through, the module will
      # think it is __main__ and it will execute itself if it is a main
      # module.
      _globals = dict(globals())
      _globals["__name__"] = os.path.basename(module_path)
      exec(infile.read(), _globals)  # pylint: disable=exec-used
  except:  # pylint: disable=bare-except
    # TODO(josh): should we log exceptions into the dependency file?
    pass

  outlist = []
  for name, value in sorted(sys.modules.items()):
    # skip ourselves
    if name in ("__main__", "__mp_main__"):
      continue

    # skip embedded modules
    if not hasattr(value, "__file__"):
      continue

    filepath = os.path.realpath(getattr(value, "__file__"))

    # e.g. <gi.repository.Atk>
    if not os.path.exists(filepath):
      continue

    # skip our module, unless the file is in our module
    if name.startswith("makelint"):
      if "makelint" not in module_path:
        continue

    if filepath.startswith(source_tree):
      filepath = os.path.relpath(filepath, source_tree)
      digest_path = target_path + ".sha1"
      with open(digest_path) as infile:
        digest = infile.read().strip()
    else:
      digest = None
    outlist.append({
        "digest": digest,
        "name": name,
        "path": filepath,
    })

  import json
  json.dump(outlist, sys.stdout, indent=2, sort_keys=True)
  sys.stdout.write("\n")


if __name__ == "__main__":
  main()
