=========
Make Lint
=========

A highly-compatible "build" system for linting python files.

-------
Purpose
-------

The purpose of this program is to lint/check your python code. Why do you
need specialized software to do this?

1. Python static analysis tools (``pylint``, ``flake8``, etc) are slow. If you
   have more than a couple dozen files then linting every file can take quite
   a long time.
2. These tools generally load the module to understand what the python code
   is doing. This means that the checker depends not just on the file you're
   checking, but the full transitive closure of it's dependencies

This program maintains a database of dependencies so that you can be confident
that a particular lint check is still valid. You can know for certain not just
that a particular file hasn't changed, but also none of the files it depends on
has changed. This allows you to skip re-checking unchanged files.

It is the intent of this project to (eventually) support standard build-systems
like ``make`` or ``ninja``, but it also implements a self-contained solution.
In particular it allows an "opt-out" workflow (rather than an opt-in) meaning
two things:

1. You don't need to re-run configure (or cmake) when you add new files
   (and, lets face it, you are probably suffering from some configure
   bloat, aren't you).
2. When new python is added to the code base, it is automatically included
   for checking. A human being must make an explicit decision to exclude it.
   Developers cannot "forget" to add it to the build system for linting.

-----
Usage
-----

.. dynamic: usage-begin

.. code:: text

    usage:
    pymakelint [-h] [-v] [-l {debug,info,warning,error}] [--dump-config]
               [-c CONFIG_FILE] [<config-overrides> [...]]

    Incremental execution system for python code analysis (linting).

    optional arguments:
      -h, --help            show this help message and exit
      -v, --version         show program's version number and exit
      -l {debug,info,warning,error}, --log-level {debug,info,warning,error}
      --dump-config         If specified, print the default configuration to
                            stdout and exit
      -c CONFIG_FILE, --config-file CONFIG_FILE
                            path to configuration file

    Configuration:
      Override configfile options

      --include-patterns [INCLUDE_PATTERNS [INCLUDE_PATTERNS ...]]
                            A list of python regular expression patterns which are
                            used to include files during the directory walk. They
                            are matched against relative paths of files (relative
                            to the root of the search). They are not matched
                            against directories. The default is `[".*\.py"]`.
      --exclude-patterns [EXCLUDE_PATTERNS [EXCLUDE_PATTERNS ...]]
                            A list of python regular expression patterns which are
                            used to exclude files during the directory walk. They
                            are matched against relative paths of files (relative
                            to the root of the search). If the pattern matches a
                            directory the whole directory is skipped. If it
                            matches an individual file then that file is skipped.
      --source-tree SOURCE_TREE
                            The root of the search tree for inclusion.
      --target-tree TARGET_TREE
                            The root of the tree where the outputs are written.
      --tools [TOOLS [TOOLS ...]]
                            A list of tools to execute. The default is ["pylint",
                            "flake8"]. This can either be a string (a simple
                            command which takes one argument), or it can be an
                            object with a get_stamp() and an execute() method. See
                            SimpleTool for ane example.
      --fail-fast [FAIL_FAST]
                            If true, exit on the first failure, don't keep going.
                            Useful if you want a speedy CI gate.
      --merged-log MERGED_LOG
                            If specified, output logs for failed jobs will be
                            merged into a single file at this location. Useful if
                            you have a large number of issues to del with.
      --quiet [QUIET]       Don't print fancy progress bars to stdout.
      --jobs JOBS           Number of parallel jobs to execute.

.. dynamic: usage-end

-------------
Configuration
-------------

Most command line options can also be specified in a configuration file.
Configuration files are python files. If not specified on the command line,
the tool will automatically look for and load the configuration file at
``<source_tree>/.makelint.py``.

You can use ``--dump-config`` to dump the default configuration to a file and
use that as a starting point. The default config is also pasted below.

.. dynamic: config-begin

.. code:: text

    # A list of python regular expression patterns which are used to include files
    # during the directory walk. They are matched against relative paths of files
    # (relative to the root of the search). They are not matched against
    # directories. The default is `[".*\.py"]`.
    include_patterns = ['.*\\.py']

    # A list of python regular expression patterns which are used to exclude files
    # during the directory walk. They are matched against relative paths of files
    # (relative to the root of the search). If the pattern matches a directory the
    # whole directory is skipped. If it matches an individual file then that file is
    # skipped.
    exclude_patterns = []

    # The root of the search tree for inclusion.
    source_tree = None

    # The root of the tree where the outputs are written.
    target_tree = None

    # A list of tools to execute. The default is ["pylint", "flake8"]. This can
    # either be a string (a simple command which takes one argument), or it can be
    # an object with a get_stamp() and an execute() method. See SimpleTool for ane
    # example.
    tools = ['flake8', 'pylint']

    # A dictionary specifying the environment to use for the tools. Add your
    # virtualenv configurations here.
    env = {
      "LANG": "en_US.UTF-8",
      "LANGUAGE": "en_US",
      "PATH": [
        "/usr/local/sbin",
        "/usr/local/bin",
        "/usr/sbin",
        "/usr/bin",
        "/sbin",
        "/bin"
      ]
    }

    # If true, exit on the first failure, don't keep going. Useful if you want a
    # speedy CI gate.
    fail_fast = False

    # If specified, output logs for failed jobs will be merged into a single file
    # at this location. Useful if you have a large number of issues to del with.
    merged_log = None

    # Don't print fancy progress bars to stdout.
    quiet = False

    # Number of parallel jobs to execute.
    jobs = 12  # multiprocessing.cpu_count()


.. dynamic: config-end

------
Design
------

.. dynamic: design-begin

Discovery/Indexing
==================

The first phase is discovery and indexing. This is done at build time, rather
than configure-time, because, let's face it, your build system already suffers
from enough configure time bloat. Also, as mentioned above, this supports an
opt-out system.

The discovery step performs a filesystem walk in order to build up an index
of files to be checked. You can use a configuration file or command line
options to setup inclusion and exclusion filters for the discovery process.
In general, though, each directory that is scanned produces a list of files to
lint. If the timestamp of a tracked directory changes, it is rescanned for new
files, or new directories.

The output of the discovery phase is a manifest file per-directory tracked.
The creation of this manifest depends on the modification time of the directory
it corresponds to and will be re-built if the directory is changed. If a new
subdirectory is added, the system will recursively index that new directory.
If a directory is removed, it will recursively purge that directory from the
manifest index.

Content Digest
==============

The second phase is content summary and digest creation. The sha1 of each
tracked file is computed and stored in a digest file (one per source file).
The digest file depends on the modification time of the source file.

Dependency Inference
====================

The third phase is dependency inference. During this phase each tracked
source file is indexed to get a complete dependency footprint. Note that this
is done by importing each module file in a clean interpreter process, and
then inspecting the ``__file__`` attribute of all modules loaded by
interpreter. Note that this has a couple of implications:

* Dynamically loaded modules may not be discovered as dependencies
* Any import work will increase the runtime of this phase

The outputs for this phase is a dependency manifest: one per source file. The
manifest contains a list of files that are dependencies. The dependencies of
this manifest are the modification times of the digest sidecar file for
each of the  source file itself, as well as all of it's dependencies. If any of
these digest files are modified, the manifest is rebuilt. There is a fastpath,
however, in that if none of the digests themselves have changed the manifest
modification time is updated but the dependency scan is skipped.

Executing tools
===============

Once the depency footprints are updated we can finally start executing the
actual tools. There are two outputs of a tool execution : a stampfile
(one per source file) and a logfile. The stampfile is skipped on failure and
the logfile is removed on success.

.. dynamic: design-end
