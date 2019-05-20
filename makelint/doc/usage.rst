=====
Usage
=====

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

-------
Example
-------

For example, executing on this project itself::

    $ time makelint --source-tree . --target-tree /tmp/makelint --jobs 1
    real	0m10.221s
    user	0m9.736s
    sys	0m0.510s
    $ time makelint --source-tree . --target-tree /tmp/makelint
    real	0m0.097s
    user	0m0.077s
    sys	0m0.020s
