"""
Update dynamic content for documentation

Execute from the `makelint` project directory with something like:

python -B doc/gendoc_sources.py
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile


def format_directive(content, codetag):
  """
  Format a block of content into restructured-text inline-code.

  Split the content it into lines and indent each line by four spaces.
  Surround it with a ".. code::" directive.
  """

  outlines = [".. code:: {}".format(codetag), ""]
  for line in content.split("\n"):
    outlines.append(("    " + line).rstrip())
  outlines.append("")
  return "\n".join(outlines)


def process_file(filepath, dynamic_text):
  """
  Create a copy of the file replacing any dynamic sections with updated
  text stored in ``dynamic_text``. Then replace the original with the updated
  copy.

  Dynamic text is identified by a sentinel restructured text comment in the
  form of ``.. dynamic: <title>-begin`` and ``.. dynamic: <title>-end``.
  """
  tag_pattern = re.compile("^.. dynamic: (.*)-(begin|end)$")
  active_section = None

  nextpath = filepath + ".next"
  with open(filepath, "r") as infile:
    with open(nextpath, "w") as outfile:
      for line in infile:
        match = tag_pattern.match(line.strip())
        if active_section is None:
          outfile.write(line)

        if match:
          if match.group(2) == "begin":
            active_section = match.group(1)
          elif match.group(2) == "end":
            assert active_section == match.group(1), (
                "Unexpected end tag {} != {}"
                .format(match.group(1), active_section))
            outfile.write("\n")
            outfile.write(dynamic_text[active_section])
            active_section = None
            outfile.write(line)
          else:
            raise RuntimeError("Unexpected tag")

  os.rename(nextpath, filepath)


CONFIG = """
env = {
  "LANG": "en_US.UTF-8",
  "LANGUAGE": "en_US",
  "PATH": ":".join([
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
  ]),
}
"""


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  _ = parser.parse_args()

  docdir = os.path.dirname(os.path.realpath(__file__))
  packagedir = os.path.dirname(docdir)
  os.chdir(packagedir)
  env = os.environ.copy()
  projectdir = os.path.dirname(packagedir)
  env["PYTHONPATH"] = projectdir

  execmodule = "makelint"

  dynamic_text = {}
  dynamic_text["usage"] = format_directive(
      subprocess.check_output(
          [sys.executable, "-Bm", execmodule, "--help"], env=env
      ).decode("utf-8"),
      "text")

  with tempfile.NamedTemporaryFile(
      mode="w", delete=False, encoding="utf-8") as outfile:
    outfile.write(CONFIG)
    configpath = outfile.name
  dynamic_text["config"] = format_directive(
      subprocess.check_output(
          [sys.executable, "-Bm", execmodule, "--config", configpath,
           "--dump-config"], env=env
      ).decode("utf-8"),
      "text")

  for basename in ["design"]:
    filename = basename + ".rst"
    with open(os.path.join(docdir, filename)) as infile:
      copylines = []
      for idx, line in enumerate(infile):
        if idx > 3:
          copylines.append(line)
      copylines.append("\n")
    dynamic_text[basename] = "".join(copylines)

  process_file("doc/README.rst", dynamic_text)
  process_file("doc/usage.rst", dynamic_text)


if __name__ == "__main__":
  main()
