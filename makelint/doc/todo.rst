====
TODO
====

--------------------
Single-file Manifest
--------------------

Think about whether or not the file manifest can be a single file.

* If any directory changes we need to run the job.
* But we wont know if a directory has changed without reading it's
  timestamp...
* Reading the timestamp means reading the directory contents of the parent,
  so we are essentially walking the tree just to check timestamps.
* If we are walking the tree anyway, is there any reason to just write the
  one big file?
* We might not want to write a new file on every invocation (seems kind of
  dirty from a build system perspective) but we can probaby whole the entire
  manifest in memory and then write it out. If we can't hold it in memory
  we could write it to a temporary location and then copy it to the goal
  location.

-----------------
Latch Environment
-----------------

* Add environmental information to the target tree, so that we know when it
  is invalidated by a change in configuration
* We probably want to include the entire config object. We need to rescan
  whenevever exclude patterns or include patterns change.. source tree,
  environment options (PYTHONPATH, etc).
* Implement ``--add-source-tree-to-python-path`` config/command line option.
  We don't want the user to have to do this in the config necessarily because
  then they can't store the config in the repo. They could "configure" the
  config but it would be nice for that not to be a requirement.

-------------------------
Makefile Jobserver Client
-------------------------

Implement GNU make jobserver client protocol

* see: `this page`__ on job slots
* see also: `this page`__ detaling the posix jobserver implementation

It's pretty easy actually. Just read the ``MAKEFLAGS`` environment variable.
If it contains ``--jobserver-auth=<R>,<W>`` then ``<R>``, ``<W>`` are integer
filedescriptors of the read and write ends of a pipe. The read end contains
one character for each job that we are allowed. For each byte we read out
of the pipe we must write one byte back to the pipe when we are done.

* See the notes on that page about what to do in various cases for some
  make invocations. In particular, you should catch SIGINT and return the
  jobs back to the server.
* Note that you always get one implicit job (that you do not return to the
  server)
* There is ongoing discussion about implementing the makefile jobserver
  client protocol (and server protocol) in ninja. Cmake already appears to
  distribute a version of ninja that supports it.
  https://github.com/ninja-build/ninja/pull/1140
* This guy has an implementation that seems to work
  https://github.com/stefanb2/ninja
* Of course, ninja has it's ``pool`` implementation, so you can probably
  skip concerns about this

.. __: https://www.gnu.org/software/make/manual/html_node/Job-Slots.html
.. __: https://www.gnu.org/software/make/manual/html_node/POSIX-Jobserver.html

-----
Other
-----

* Implement sqlite database backend (versus filesystem)
* Change the name of this package/project
* Add a ``--whitelist`` command-line/config argument. Rather than secifying
  a large list of exact filenames in the exclusion patterns, this can be a
  set that we efficiently check for inclusion in.
* Implement ``dlsym`` checking to get a list of python modules that are loaded
* Implement a ``--merge-env`` option to merge the configured environment
  into the runtime environment.
