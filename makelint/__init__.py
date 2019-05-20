# -*- coding: utf-8 -*-
import collections
import hashlib
import logging
import json
import os
import fcntl
import shutil
import subprocess
import sys
import time

VERSION = '0.0.1'
DEPENDENCY_SUFFIX = ".dep"
MANIFEST_FILENAME = "manifest.txt"
SUCCESS_STAMP = ".success"
FAIL_STAMP = ".fail"

logger = logging.getLogger()


def waitforsize(pidset, njobs):
  """
  Given a set() of pids, wait until it has at most njobs alive children
  """
  output = 0
  while len(pidset) > njobs:
    pid, status = os.wait()
    pidset.remove(pid)
    output |= status
  return output


def discover_sourcetree(
    source_tree, target_tree, exclude_patterns, include_patterns,
    progress):
  """
  The discovery step performs a filesystem walk in order to build up an index
  of files to be checked. You can use configuration files to setup inclusion
  and exclusion filters for the discovery process. In general, though, each
  directory that is scanned produces a list of files to lint. If the timestamp
  of a tracked directory changes, it is rescanned for new files, or new
  directories.

  The output of the discovery phase is a manifest file per-directory tracked.
  The creation of this manifest depends on the modification time of the
  directory it corresponds to and will be re-built if the directory is changed.
  If a new subdirectory is added, the system will recursively index that new
  directory. If a directory is removed, it will recursively purge that
  directory from the manifest index.
  """

  if not os.path.exists(target_tree):
    os.makedirs(target_tree)

  ndirs = 1
  dir_idx = 0
  for source_cwd, dirnames, filenames in os.walk(source_tree):
    dir_idx += 1
    progress(dir_idx=dir_idx, ndirs=ndirs)
    relpath_cwd = os.path.relpath(source_cwd, source_tree)
    if relpath_cwd == ".":
      # NOTE(josh): os.path.join("", "foo") == "foo"
      relpath_cwd = ""

    target_cwd = os.path.join(target_tree, relpath_cwd)
    if not os.path.exists(target_cwd):
      os.makedirs(target_cwd)

    # NOTE(josh): is it faster to re-apply filters? or load the result
    # from the manifest?
    filtered_dirnames = []
    for dirname in sorted(dirnames):
      if dirname in (".", ".."):
        continue
      relpath_dir = os.path.join(relpath_cwd, dirname)
      if any(pattern.match(relpath_dir) for pattern in exclude_patterns):
        continue
      filtered_dirnames.append(dirname)

    # Only recurse on directories that are tracked
    dirnames[:] = filtered_dirnames
    ndirs += len(filtered_dirnames)

    manifest_path = os.path.join(target_cwd, MANIFEST_FILENAME)
    if (os.path.exists(manifest_path) and
        os.path.getmtime(manifest_path) > os.path.getmtime(source_cwd)):
      # NOTE(josh): this directory has not changed since the last time that
      # we scanned it, so we do not need to rewrite the manifest
      continue
    logger.debug("Scanning: %s", source_cwd)

    filtered_filenames = []
    for filename in sorted(filenames):
      relpath_file = os.path.join(relpath_cwd, filename)
      if any(pattern.match(relpath_file) for pattern in exclude_patterns):
        continue
      if any(pattern.match(relpath_file) for pattern in include_patterns):
        filtered_filenames.append(filename)

    source_dirset = set(dirnames)
    target_dirset = set(dirent.name for dirent in os.scandir(target_cwd)
                        if dirent.is_dir())

    # Directories in the target tree which are not tracked in the source
    # tree. We need to remove them
    for dirname in target_dirset.difference(source_dirset):
      shutil.rmtree(os.path.join(target_cwd, dirname))

    with open(manifest_path, "w") as outfile:
      for filename in filtered_filenames:
        if any(pattern.match(relpath_dir) for pattern in exclude_patterns):
          continue
        outfile.write(filename)
        outfile.write("\n")

  progress(dir_idx=ndirs)


def chunk_iter_file(infile, chunk_size=4096):
  """
  Read a file chunk by chunk
  """
  chunk = infile.read(chunk_size)
  while chunk != b"":
    yield chunk
    chunk = infile.read(chunk_size)


def digest_file(source_path, digest_path):
  """
  Compute a message digest of the file content, write the digest
  (in hexadecimal ascii encoding) to the output file
  """
  hasher = hashlib.sha1()
  with open(source_path, "rb") as infile:
    for chunk in chunk_iter_file(infile):
      hasher.update(chunk)
  with open(digest_path, "w") as outfile:
    outfile.write(hasher.hexdigest())
    outfile.write("\n")


def digest_sourcetree_content(source_tree, target_tree, progress, njobs):
  """
  The sha1 of each tracked file is computed and stored in a digest file
  (one per source file). The digest file depends on the modification time of
  the source file. If the sourcefile hasn't changed, the digest file doesn't
  need to be updated.
  """

  progress(tool_idx=1, tool="sha1")
  pidset = set()
  file_idx = 0
  nfiles = 0
  for target_cwd, dirnames, filenames in os.walk(target_tree):
    dirnames[:] = sorted(dirnames)  # stable walk

    relpath_cwd = os.path.relpath(target_cwd, target_tree)
    if relpath_cwd == ".":
      # NOTE(josh): os.path.join("", "foo") == "foo"
      relpath_cwd = ""
    source_cwd = os.path.join(source_tree, relpath_cwd)

    manifest_path = os.path.join(target_cwd, MANIFEST_FILENAME)
    with open(manifest_path) as infile:
      filenames = list(line.strip() for line in infile)

    nfiles += len(filenames)
    progress(nfiles=nfiles)
    for filename in sorted(filenames):
      file_idx += 1
      progress(file_idx=file_idx)
      digest_name = filename + ".sha1"
      source_path = os.path.join(source_cwd, filename)
      digest_path = os.path.join(target_cwd, digest_name)
      if (os.path.exists(digest_path) and
          os.path.getmtime(digest_path) > os.path.getmtime(source_path)):
          # NOTE(josh): this source file has not changed since the last time
          # that we digested it, so we do not need to
        continue
      logger.debug("Digesting: %s/%s", relpath_cwd, filename)
      waitforsize(pidset, njobs - 1)
      pid = os.fork()
      if pid == 0:
        digest_file(source_path, digest_path)
        os._exit(0)  # pylint: disable=protected-access
      pidset.add(pid)
  waitforsize(pidset, 0)


# pylint: disable=E1123
if sys.version_info < (2, 6, 0):
  DependencyItem = collections.namedtuple(
      "DependencyItem", ["path", "digest", "name"])
  DependencyItem.__new__.func_defaults = (None,)
if sys.version_info < (3, 7, 0):
  DependencyItem = collections.namedtuple(
      "DependencyItem", ["path", "digest", "name"])
  DependencyItem.__new__.__defaults__ = (None,)
else:
  DependencyItem = collections.namedtuple(
      "DependencyItem", ["path", "digest", "name"],
      defaults=(None,))


def depmap_is_uptodate(target_tree, relpath_file):
  """
  Given a dictionary of dependency data, return true if all of the files
  listed are unchanged since we last ran the scan.f
  """
  relpath_depmap = relpath_file + DEPENDENCY_SUFFIX
  depmap_path = os.path.join(target_tree, relpath_depmap)

  if not os.path.exists(depmap_path):
    return False
  if not os.path.exists(depmap_path + ".sha1"):
    return False

  depmap_mtime = os.path.getmtime(depmap_path)
  if os.path.getmtime(depmap_path + ".sha1") < depmap_mtime:
    logger.warning("depmap mtime is later than it's sha1")
    return False

  with open(depmap_path, "r") as infile:
    depmap_data = json.load(infile)

  for item in depmap_data:
    item = DependencyItem(**item)

    if item.path.startswith("/"):
      if not os.path.exists(item.path):
        logger.debug("%s disappeared", item.path)
        return False

      # The dependency is an absolute path, which means that it is outside
      # the source tree. We don't have a digest cache of this file so if
      # it's timestamp indictes it is newer we must act on taht.
      if os.path.getmtime(item.path) > depmap_mtime:
        logger.debug("%s is newer", item.path)
        return False
      continue

    digest_path = os.path.join(target_tree, item.path + ".sha1")
    if not os.path.exists(digest_path):
      # Digest file does not exist, but corresponding source file is in our
      # source tree... so it must have been excluded during scan
      if not os.path.exists(item.path):
        logger.debug("%s disappeared", item.path)
        return False

      if os.path.getmtime(item.path) > depmap_mtime:
        logger.debug("%s is newer", item.path)
        return False
      continue

    if os.path.getmtime(digest_path) < depmap_mtime:
      # The dependency map is newer than this particular file, so this
      # file does not invalidate it
      continue

    with open(digest_path) as infile:
      digest = infile.read().strip()

    if digest == item.digest:
      # The timestamp on this file is newer than the digest, but the file
      # content is unchanged, so thsi file does not invalidate it
      continue

    # The timestamp is newer and it's content has changed. The dependency
    # map is out of date.
    return False
  return True


def map_dependencies(source_tree, target_tree, source_relpath):
  """
  Get a dependency list from the sourcefile. Writeout the dependency file
  and it's sha1 digest.
  """
  targetpath = os.path.join(target_tree, source_relpath) + DEPENDENCY_SUFFIX
  with open(targetpath, "w") as outfile:
    subprocess.check_call(
        [sys.executable, "-Bm", "makelint.get_dependencies",
         "--module-relpath", source_relpath,
         "--source-tree", source_tree,
         "--target-tree", target_tree
         ], stdout=outfile, stderr=subprocess.DEVNULL)
  digest_file(targetpath, targetpath + ".sha1")


def map_sourcetree_dependencies(source_tree, target_tree, progress, njobs):
  """
  During this phase each tracked
  source file is indexed to get a complete dependency footprint. Note that this
  is done by importing each module file in a clean interpreter process, and
  then inspecting the `__file__` attribute of all modules loaded by interpreter.
  """
  progress(tool_idx=2, tool="depmap")
  pidset = set()
  file_idx = 0
  for target_cwd, dirnames, filenames in os.walk(target_tree):
    dirnames[:] = sorted(dirnames)  # stable walk

    relpath_cwd = os.path.relpath(target_cwd, target_tree)
    if relpath_cwd == ".":
      # NOTE(josh): os.path.join("", "foo") == "foo"
      relpath_cwd = ""

    manifest_path = os.path.join(target_cwd, MANIFEST_FILENAME)
    with open(manifest_path) as infile:
      filenames = list(line.strip() for line in infile)

    for filename in sorted(filenames):
      file_idx += 1
      progress(file_idx=file_idx)
      relpath_file = os.path.join(relpath_cwd, filename)
      if not depmap_is_uptodate(target_tree, relpath_file):
        logger.debug("Mapping dependencies: %s", relpath_file)
        waitforsize(pidset, njobs - 1)
        pid = os.fork()
        if pid == 0:
          map_dependencies(source_tree, target_tree, relpath_file)
          os._exit(0)  # pylint: disable=protected-access
        pidset.add(pid)
  waitforsize(pidset, 0)


def toolstamp_is_uptodate(toolstamp_path, depmap_path):
  """
  Return true if the toolstamp is up to date with respect to the dependency
  map
  """
  digest_path = depmap_path + ".sha1"
  if not os.path.exists(toolstamp_path):
    return False

  if os.path.getmtime(toolstamp_path) > os.path.getmtime(depmap_path):
    # The tool execution stamp is newer than the dependency map digest
    # so we know that it is up to date
    return True

  with open(toolstamp_path) as infile:
    toolstamp_digest = infile.read().strip()

  with open(digest_path) as infile:
    depmap_digest = infile.read().strip()

  # If the current dependency map digest matches the dependency map digest
  # when the tool was last executed, then the dependency footprint has not
  # changed (nor the source file itself) so the tool stamp is up to date.
  return toolstamp_digest == depmap_digest


def cat_log(logfile_path, header, merged_log):
  """
  Copy the content from logfile_path into merged_log
  """
  if not merged_log:
    return

  merged_log.write(header)
  merged_log.write("\n")
  merged_log.write("=" * len(header))
  merged_log.write("\n")
  with open(logfile_path) as infile:
    for line in infile:
      merged_log.write(line)
  merged_log.write("\n\n")


def execute_tool_ontree(
    source_tree, target_tree, tool, env, fail_fast, merged_log, progress,
    njobs):
  """
  Execute the given tool
  """
  progress(tool_idx=progress.tool_idx + 1, tool=tool.name)
  pidset = set()
  file_idx = 0
  output = 0
  for target_cwd, dirnames, filenames in os.walk(target_tree):
    dirnames[:] = sorted(dirnames)  # stable walk

    relpath_cwd = os.path.relpath(target_cwd, target_tree)
    if relpath_cwd == ".":
      # NOTE(josh): os.path.join("", "foo") == "foo"
      relpath_cwd = ""

    manifest_path = os.path.join(target_cwd, MANIFEST_FILENAME)
    with open(manifest_path) as infile:
      filenames = list(line.strip() for line in infile)

    for filename in sorted(filenames):
      file_idx += 1
      progress(file_idx=file_idx)
      source_relpath = os.path.join(relpath_cwd, filename)
      toolstamp_path = tool.get_stamp(target_cwd, filename)
      depmap_path = os.path.join(target_cwd, filename + DEPENDENCY_SUFFIX)
      logfile_path = toolstamp_path + ".log"

      if toolstamp_is_uptodate(toolstamp_path, depmap_path):
        with open(toolstamp_path) as infile:
          content = infile.read().strip()
        if content == "fail":
          output |= 1
          header = "{} (cached)".format(source_relpath)
          cat_log(logfile_path, header, merged_log)
          if fail_fast:
            return output
      else:
        if os.path.exists(toolstamp_path):
          os.remove(toolstamp_path)

        output |= waitforsize(pidset, njobs - 1)
        if fail_fast and output:
          output |= waitforsize(pidset, 0)
          return output

        pid = os.fork()
        if pid != 0:
          pidset.add(pid)
          continue

        # Child process
        with open(logfile_path, "w") as outfile:
          result = tool.execute(source_tree, source_relpath, env, outfile)
        if result == 0:
          logger.debug("%s: okay!", toolstamp_path)
          shutil.copyfile(depmap_path + ".sha1", toolstamp_path)
          os.remove(logfile_path)
        else:
          with open(toolstamp_path, "w") as outfile:
            outfile.write("fail")
          logger.info("%s: failed :(", toolstamp_path)

          # NOTE(josh): we have multiple processes catting to this file, so
          # we need serialize the cat operation to prevent interleaving.
          fcntl.flock(merged_log, fcntl.LOCK_EX)
          cat_log(logfile_path, source_relpath, merged_log)
          fcntl.flock(merged_log, fcntl.LOCK_UN)
        merged_log.close()
        os._exit(result)  # pylint: disable=protected-access

  output |= waitforsize(pidset, 0)
  return output


def get_progress_bar(numchars, fraction=None, percent=None):
  """
  Return a high resolution unicode progress bar
  """
  if percent is not None:
    fraction = percent / 100.0

  if fraction >= 1.0:
    return "█" * numchars

  blocks = [" ", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
  length_in_chars = fraction * numchars
  n_full = int(length_in_chars)
  i_partial = int(8 * (length_in_chars - n_full))
  n_empty = max(numchars - n_full - 1, 0)
  return ("█" * n_full) + blocks[i_partial] + (" " * n_empty)


class ProgressReporter(object):
  """
  Prints a status message
  """

  def __init__(self):
    self.ndirs = 0
    self.nfiles = 0
    self.ntools = 0

    self.dir_idx = 0
    self.tool_idx = 0
    self.file_idx = 0

    self.tool = ""
    self.lastprint = 0
    self.toolnames = [""] * 10

  def __call__(self, **kwargs):
    rewind = kwargs.pop("rewind", True)
    force = kwargs.pop("force", False)

    if "tool_idx" in kwargs and "tool" in kwargs:
      self.toolnames[kwargs["tool_idx"]] = kwargs["tool"]

    for key, value in kwargs.items():
      setattr(self, key, value)

    if time.time() - self.lastprint < 0.1 and not force:
      return

    self.lastprint = time.time()
    nlines = self.do_print()

    if rewind:
      # Move back up three lines
      sys.stdout.write("\x1b[{}F".format(nlines))
    sys.stdout.flush()

  def get_nsteps(self):
    """
    Return the total number of steps to completion
    """
    return self.nfiles + (self.ntools * self.nfiles)

  def get_istep(self):
    """
    Return the index of our current step
    """
    return (self.tool_idx * self.nfiles) + self.file_idx

  def get_progress(self):
    """
    Return current progress as a percentage
    """
    if self.get_nsteps() == 0:
      return 0
    return 100.0 * self.get_istep() / self.get_nsteps()

  def do_print(self):
    nlines = 0

    sys.stdout.write(
        "{:>10s}: {:5d}/{:<5d} [{}] {:6.2f}%"
        .format("Total", self.get_istep(), self.get_nsteps(),
                get_progress_bar(20, percent=self.get_progress()),
                self.get_progress())
    )
    sys.stdout.write("\x1b[0K\n")  # clear the rest of the line
    nlines += 1

    progress = 0.0
    if self.ndirs > 0:
      progress = 100.0 * self.dir_idx / self.ndirs
    sys.stdout.write(
        "{:>10s}: {:5d}/{:<5d} [{}] {:6.2f}%"
        .format("Indexing", self.dir_idx, self.ndirs,
                get_progress_bar(20, percent=progress),
                progress))
    sys.stdout.write("\x1b[0K\n")  # clear the rest of the line
    nlines += 1

    for idx in range(1, self.tool_idx):
      sys.stdout.write(
          "{0:>10s}: {1:5d}/{1:<5d} [{2}] {3:6.2f}%"
          .format(self.toolnames[idx], self.nfiles,
                  get_progress_bar(20, 1.0), 100.0))
      sys.stdout.write("\x1b[0K\n")
      nlines += 1

    if self.tool_idx > 0:
      progress = 0.0
      if self.nfiles > 0:
        progress = 100.0 * self.file_idx / self.nfiles
      sys.stdout.write(
          "{:>10s}: {:5d}/{:<5d} [{}] {:6.2f}%"
          .format(self.tool, self.file_idx, self.nfiles,
                  get_progress_bar(20, percent=progress),
                  progress))
    sys.stdout.write("\x1b[0K\n")  # clear the rest of the line
    nlines += 1

    return nlines


class NullProgressReport(object):
  """
  No-op for quiet mode
  """

  def __call__(self, *kwargs):
    pass
