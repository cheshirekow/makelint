======
Design
======

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
