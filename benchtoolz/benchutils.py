from __future__ import print_function
import glob
import imp
import inspect
import os.path
import pyclbr
import sys
import textwrap
import timeit
from .printutils import ProgressPrinter, BenchPrinter, nsorted

# We can introduce better configuration handling later.
# We should, however, think about and clean up the *values* of these configs.
default_dirs = ['*arena*', '*benchmark*', '*benchit*']
default_arenaprefixes = ['', 'trial_', 'arena_']
default_benchprefixes = ['benchit_', 'bench_', 'timeit_', 'time_']
default_mintime = 0.25
default_numrepeat = 3
default_timer = timeit.default_timer


class BenchRunner(object):
    """ A class that makes it easy to find, run, and display benchmark results.

    This gives the user more control than ``quickstart``, and is a thin
    wrapper over functions such as ``findarenas``, ``findbenchmarks``, and
    ``runbenchmarks``.

    Initialization: determine source directory, prefixes, and path patterns.
    If keywords arenaprefixes, benchprefixes, arenapaths, and benchpaths are
    not given, then default values will be used (and calculated as applicable).
    The user can inspect and modify these attributes after the BenchRunner has
    been created.

    Finding arenas and benchmarks: call ``findarenas`` and ``findbenchmarks``
    methods to get dicts that map filenames to list of function names to use in
    the benchmarks.  No file will be imported (unless cython is True), so this
    is a safe operation.  The user may modify the dicts if desired.

    Running benchmarks: run the benchmarks.  If ``arenadict`` and ``benchdict``
    aren't passed to ``BenchRunner.runbenchmarks``, then the values returned by
    ``findarenas`` and ``findbenchmarks`` will be used.

    Display the benchmarks: currently only github-flavored markdown tables are
    supported.  Tables can be of time, relative time, and rank.

    """
    # Uses: getsourcedir, getpaths, findarenas, findbenchmarks, runbenchmarks
    def __init__(self, name, cython=False, arenaprefixes=default_arenaprefixes,
                 benchprefixes=default_benchprefixes, sourcedir=None,
                 arenapaths=None, benchpaths=None):
        self.name = name
        self.cython = cython
        self.arenaprefixes = list(arenaprefixes)
        self.benchprefixes = list(benchprefixes)
        if sourcedir is None:
            sourcedir = getsourcedir()
        self.sourcedir = sourcedir
        if arenapaths is None:
            arenapaths = getpaths(name, sourcedir=sourcedir,
                                  prefixes=self.arenaprefixes)
        self.arenapaths = list(arenapaths)
        if benchpaths is None:
            benchpaths = getpaths(name, sourcedir=sourcedir,
                                  prefixes=self.benchprefixes)
        self.benchpaths = list(benchpaths)

    def findarenas(self):
        """ Return dict that maps filenames to list of func names to benchmark.

        This is a thin wrapper around ``findarenas`` function, so see that
        function for more detail.
        """
        return findarenas(self.name, prefixes=self.arenaprefixes,
                          paths=self.arenapaths, cython=self.cython)

    def findbenchmarks(self):
        """ Return dict that maps filenames to list of benchmark func names.

        This is a thin wrapper around ``findbenchmarks`` function, so see
        that function for more detail.
        """
        return findbenchmarks(self.name, prefixes=self.benchprefixes,
                              paths=self.benchpaths)

    def runbenchmarks(self, arenadict=None, benchdict=None, verbose=True,
                      mintime=default_mintime, numrepeat=default_numrepeat,
                      timer=default_timer, trialfilter=None, trialcallback=None):
        """ Thin wrapper around ``runbenchmarks`` to run the benchmarks.

        If ``arenadict`` and ``benchdict`` are not provided, then the values
        returned by ``self.findarenas()`` and ``self.findbenchmarks()`` will
        be used by default.

        See ``runbenchmarks`` for more detail.
        """
        if arenadict is None:
            arenadict = self.findarenas()
        if benchdict is None:
            benchdict = self.findbenchmarks()
        return runbenchmarks(self.name, arenadict, benchdict, verbose=verbose,
                             mintime=mintime, numrepeat=numrepeat,
                             timer=timer, cython=self.cython,
                             trialfilter=trialfilter,
                             trialcallback=trialcallback)

    def to_gfm(self, results, relative=False, rank=False):
        """ Return a github-flavored markdown table of benchmark results.

        By default, the values in the table will be the times of the
        benchmarks.  Use ``relative=True`` keyword to display the relative
        times of the benchmarks (relative to the fastest function being
        benchmark), and use ``rank=True`` keyword to display the rank--from
        fastest (1) to slowest--of each function being benchmarked.
        """
        arenaprefixes = [prefix + self.name for prefix in self.arenaprefixes]
        printer = BenchPrinter(results, arenaprefixes=arenaprefixes,
                               benchprefixes=self.benchprefixes)
        resultlist = []
        for (benchfile, arenafile), table in sorted(printer.tables.items()):
            val = printer.to_gfm(table, relative=relative, rank=rank)
            resultlist.append((arenafile, benchfile, val))
        return resultlist


def getsourcedir():
    """ Try to return the source directory of the current "__main__" script.

    This is the default source directory to use when globbing for benchmark
    or arenafiles.

    For typical usage, benchmarks will be run via a script that is in the
    same directory as the benchmark and arena directories.  This function
    tries to determine the directory of that script (and should typically
    succeed).  If source directory cannot be determined, the current working
    directory is returned.
    """
    # Used by: getpaths, BenchRunner
    try:
        filepath = sys.modules['__main__'].__file__
    except AttributeError:
        filepath = ''
    return os.path.dirname(filepath)


def getpaths(name, sourcedir=None, dirs=None, prefixes=None):
    """ Return a list of path patterns constructed from the given arguments.

    If arguments are not given, then default values will be used, which
    should be okay if normal conventions are being used.

    Essentially, this does ``os.path.join(sourcedir, dirname, prefix + name)``
    for each dirname in ``dir`` and each prefix in ``prefixes``.

    Arguments:

        - sourcedir: directory containing arena or benchmark ``dirs``
        - dirs: list of path patterns of arena or benchmark directories
            - For example, "*benchmark*"
        - prefixes: list of prefixes used to identify arena or benchmark files
            - For example, "bench_"
    """
    # Uses: getsourcedir
    # Used by: findarenas, findbenchmarks, BenchRunner, quickstart
    if prefixes is None:
        prefixes = default_arenaprefixes + default_benchprefixes
    if sourcedir is None:
        sourcedir = getsourcedir()
    if dirs is None:
        dirs = default_dirs
    paths = []
    for dirname in dirs:
        for prefix in prefixes:
            path = os.path.join(sourcedir, dirname, prefix + name)
            paths.append(path)
    return paths


def scanfuncs(filename, prefixes, cython=False):
    """ Return list of function names from ``filename`` that begin with prefix.

    This *does not* import the Python file, so this is safe to use, but
    functionality is limited to retrieving names of basic functions defined
    within global scope of the file.

    This *does*, however, import Cython files (if applicable).
    """
    # Used by: findarenas, findbenchmarks
    path, name = os.path.split(filename)
    name, ext = os.path.splitext(name)
    # Should `cython` be a keyword argument, or should we just infer it?
    cython = cython or ext == '.pyx'
    if not cython:
        funcs = pyclbr.readmodule_ex(name, [path])
        funcnames = []
        for key, val in funcs.items():
            if (any(key.startswith(prefix) for prefix in prefixes) and
                    val.file == filename):
                funcnames.append(key)
        return funcnames

    # Scan Cython file.  We need to import it.
    import pyximport
    pyximport.install()
    sys.dont_write_bytecode = True
    # Make sure local imports work for the given file
    sys.path.insert(0, path)
    pyximport.build_module(name, filename)
    try:
        mod = pyximport.load_module(name, filename)
    except ImportError:
        # There is most likely a '*.py' file that shares the same
        # base name as the '*.pyx' file we are trying to import.
        # Removing the directory from sys.path should fix this,
        # but will disable local importing.
        sys.path.pop(0)
        mod = pyximport.load_module(name, filename)
    # Undo making local imports work
    if sys.path[0] == path:
        sys.path.pop(0)
    funcnames = []
    for funcname in mod.__dict__:
        if any(funcname.startswith(prefix) for prefix in prefixes):
            funcnames.append(funcname)
    return funcnames


def findarenas(name, cython=False, prefixes=default_arenaprefixes, paths=None):
    """ Return dict that maps filenames to list of function names to benchmark.

    This finds all functions that will be used in the benchmarks.  If
    arguments are not given, then default values will be used, which should
    be okay if normal conventions are being used.

    This *does not* import Python files, but it *does* import Cython files.
    Hence, this is a safe operation, and the user may modify the lists of
    the returned function names before any external file is imported.

    Arguments:

        - name: the base function name that is being benchmarked
        - cython: boolean, use cython files or python files
        - prefixes: list of prefixes that may come before ``name``
            - applies to filenames (if ``path`` isn't specified) and functions
        - paths: list of patterns that should glob to filenames to use
    """
    # Uses: scanfuncs
    # Used by: BenchRunner, quickstart
    if paths is None:
        paths = getpaths(name, prefixes=prefixes)
    suffix = '.pyx' if cython else '.py'
    filenames = []
    for pattern in paths:
        if not pattern.endswith(suffix):
            pattern += suffix
        filenames.extend(glob.glob(pattern))
    arenadict = {}
    for filename in filenames:
        funcprefixes = [prefix + name for prefix in prefixes]
        funcs = scanfuncs(filename, funcprefixes, cython=cython)
        if funcs:
            arenadict[filename] = funcs
    return arenadict


def findbenchmarks(name, prefixes=default_benchprefixes, paths=None):
    """ Return dict that maps filenames to list of benchmark function names.

    This finds all functions that will be used to perform the benchmarks.
    If arguments are not given, then default values will be used, which
    should be okay if normal conventions are being used.

    This *does not* import Python files.  Hence, this is a safe operation,
    and the user may modify the lists of the returned function names before
    any external file is imported.

    Arguments:

        - name: the base function name that is being benchmarked
        - prefixes: list of prefixes that identify benchmark functions
            - also applies to filenames if ``path`` isn't specified
        - paths: list of patterns that should glob to filenames to use
    """
    # Uses: scanfuncs
    # Used by: BenchRunner, quickstart
    if paths is None:
        paths = getpaths(name, prefixes=prefixes)
    suffix = '.py'
    filenames = []
    for pattern in paths:
        if not pattern.endswith(suffix):
            pattern += suffix
        filenames.extend(glob.glob(pattern))
    benchdict = {}
    for filename in filenames:
        funcs = scanfuncs(filename, prefixes, cython=False)
        if funcs:
            benchdict[filename] = funcs
    return benchdict


def getarenasetup(name, filename, funcnames, cython=False):
    """ Return dict that maps function name to setup string required by timeit.

    This *does not* import any files.
    """
    # Used by: getarenalist
    setupdict = {}
    for funcname in funcnames:
        path, modname = os.path.split(filename)
        modname, ext = os.path.splitext(name)
        func_setup = """
            sys.path.insert(0, '{path}')
            %s
            sys.path.pop(0)
            globals()['{name}'] = getattr(mod, '{funcname}')
        """
        if cython:
            load_mod = """
            import pyximport
            pyximport.install()
            pyximport.build_module('{modname}', '{filename}')
            mod = pyximport.load_module('{modname}', '{filename}')
            """
        else:
            load_mod = """
            mod = imp.load_source('_benchmark_arena_{modname}', '{filename}')
            """
        # format text, removing leading spaces, then remove empty lines
        text = func_setup % load_mod
        text = text.format(path=path, name=name, filename=filename,
                           funcname=funcname, modname=modname)
        text = textwrap.dedent(text)
        text = ''.join(filter(str.strip, text.splitlines(True)))
        setupdict[funcname] = text
    return setupdict


def getbenchsetup(filename):
    """ Return setup string required by timeit for the given benchmark file.

    This *does not* import any files.
    """
    # Used by: getbenchlist
    path, name = os.path.split(filename)
    name, ext = os.path.splitext(name)
    text = """
        import imp
        import os.path
        import sys
        sys.path.insert(0, '{path}')
        mod = imp.load_source('_benchmark_file_{name}', '{filename}')
        sys.path.pop(0)
        globals().update(mod.__dict__)
    """
    # format text, removing leading spaces, then remove empty lines
    text = text.format(path=path, filename=filename, name=name)
    text = textwrap.dedent(text)
    text = ''.join(filter(str.strip, text.splitlines(True)))
    return text


def getbenchstrings(filename, benchnames):
    """ Return dict of benchmark names to benchmark strings required by timeit.

    We benchmark using the function body.  We don't call the function directly,
    because this would add the overhead of a function call to the benchmarks.
    The last line of the function may be a return statement.

    **Warning:** this imports the file.
    """
    # Used by: getbenchlist
    # I bet somebody clever can make this function much better!
    sys.dont_write_bytecode = True
    path, name = os.path.split(filename)
    name, ext = os.path.splitext(name)
    # make sure local imports work for benchmark file
    sys.path.insert(0, path)
    mod = imp.load_source('_benchmark_file_' + name, filename)
    benchstrings = {}
    for benchname in benchnames:
        lines, lineno = inspect.getsourcelines(getattr(mod, benchname))
        # Remove "return" from final line in function.  This does not
        # work for multi-line returns!  It also fails when there are
        # multiple spaces between "return" and the next token.
        # Also, is this the correct place to strip "return"?  We may
        # want to compare outputs to verify each variant is the same.
        lastline = lines[-1].strip()
        if lastline.startswith('return '):
            lines[-1] = lines[-1].replace('return ', '', 1)
        elif lastline.startswith('return('):
            lines[-1] = lines[-1].replace('return', '', 1)
        elif lastline == 'return':
            lines.pop()
        # Skip the function definition.  This will fail if function
        # definition takes more than one line.
        benchstrings[benchname] = textwrap.dedent(''.join(lines[1:]))
    # undo making local imports work
    sys.path.pop(0)
    return benchstrings


def getarenalist(name, arenadict, cython=False):
    """ Get arena function info and flatten into a sorted list of tuples.

    The ``arenadict`` argument is a dict that maps filename to list of
    arena function names (see ``findarenas`` function).

    The returned list of tuples contain the following:

        - arenafile: filename of the current arena file
        - arenaname: name of the current arena function
        - arenasetup: setup code for ``timeit`` for current arena function

    This *does not* import the arena files.
    """
    # Uses: getarenasetup
    # Used by: runbenchmarks
    arenalist = []
    for arenafile, funcnames in arenadict.items():
        setupdict = getarenasetup(name, arenafile, funcnames, cython=cython)
        for arenaname, arenasetup in setupdict.items():
            arenalist.append((arenafile, arenaname, arenasetup))
    # Sort arena functions by filename and arena function name
    arenalist = nsorted(arenalist)
    return arenalist


def getbenchlist(benchdict):
    """ Get benchmark info and flatten into a sorted list of tuples.

    The ``benchdict`` argument is a dict that maps filename to list of
    benchmark function names (see ``findbenchmarks`` function).

    The returned list of tuples contain the following:

        - benchfile: filename of the benchmark
        - benchname: name of the current benchmark function
        - benchsetup: setup code for ``timeit`` for current ``benchfile``
        - benchmark: string of the current benchmark for ``timeit``

    **Warning:** this imports the benchmark files.
    """
    # Uses: getbenchsetup, getbenchstrings
    # Used by: runbenchmarks
    benchlist = []
    for benchfile, funcnames in benchdict.items():
        benchsetup = getbenchsetup(benchfile)
        stringdict = getbenchstrings(benchfile, funcnames)
        for benchname, benchstring in stringdict.items():
            benchlist.append((benchfile, benchname, benchsetup, benchstring))
    # Sort benchmarks by filename and benchmark function name
    benchlist = nsorted(benchlist)
    return benchlist


def bettertimeit(statements, setup, mintime=default_mintime,
                 numrepeat=default_numrepeat, timer=default_timer):
    """ A better way to use ``timeit`` when comparing benchmarks and functions.

    Like ``timeit`` when run as main and ``%timeit`` in IPython, this function
    adaptively determines the number of iterations required to achieve the
    minimum required runtime of the benchmark, ``mintime``.  However, instead
    of the loop number being a power of ten, the loop number used in this
    function is a power of two.  This has two important consequences:
    (1) benchmarks that have comparable performance will use similar numbers
    of loop iterations, and (2) the time spent running the benchmarks will
    be more consistent and will often run faster, because the runtime will
    typically be between [mintime, 2*mintime] instead of [mintime, 10*mintime].

    The arguments ``statements``, ``setup``, ``timer``, and ``numrepeat`` are
    passed directly to ``timeit.Timer`` and ``timeit.Timer.repeat``.

    Returns a list of times (in seconds) and the number of loop iterations.
    """
    # Used by: runbenchmarks
    timer = timeit.Timer(statements, setup, timer=timer)
    # Use powers of two so tests are likely to use comparable iteration
    # numbers if they have comparable performance.
    loops = 1
    for i in range(32):
        runtime = timer.timeit(loops)
        # We can save the most amount of time by skipping iterations close
        # to the final loop number, and the time is not likely to change
        # significantly when the loop count changes by a factor of 8.
        if runtime > mintime:
            break
        elif runtime > mintime / 2.0:
            loops *= 2
        elif runtime > mintime / 4.0:
            loops *= 4
        elif runtime > mintime / 8.0:
            loops *= 8
        elif runtime > mintime / 16.0:
            loops *= 2  # aim short (to x8)
        elif runtime > mintime / 32.0:
            loops *= 8  # aim short (to x4)
        elif runtime > mintime / 64.0:
            loops *= 8  # aim short (to x8)
        else:
            loops *= 2
    # Should we use the previous run as "burn in", or should we include it?
    results = timer.repeat(numrepeat - 1, loops)
    results.append(runtime)
    results = [x / loops for x in results]
    return results, loops


def runbenchmarks(name, arenadict, benchdict, verbose=True, cython=False,
                  mintime=default_mintime, numrepeat=default_numrepeat,
                  timer=default_timer, trialfilter=None, trialcallback=None):
    """ Run all benchmarks in ``benchdict`` with functions from ``arenadict``.

    ``arenadict`` and ``benchdict`` should be dicts of filenames to lists of
    function names, such as ``{filename: [funcname1, funcname2]}``.

    Keyword arguments:

        - verbose: if True, print benchmark results to stdout in real-time.
        - cython: run the tests on Python (if False) or Cython files (if True).
        - mintime: minimum amount of time for each benchmark to run.
        - numrepeat: number of times to repeat each benchmark.
        - timer: the timer to use during the benchmarks.
        - trialfilter: a callback function that allows the user to inspect the
          benchmark that is about to be run.  If it returns False, then the
          benchmark is skipped.  The callback function should accept a single
          argument, which is a dictionary with items as desribed below.
        - trialcallback: this callback is called *after* the benchmark, and it
          is given the same dict as ``trialfilter``.  If it returns False,
          then *all* benchmarking is stopped.  This can be used, for example,
          to print or save benchmark results in real-time.

    The trial dict passed to trialfilter and trialcallback has these items:

        - arenafile: filename that contains the function being benchmarked
        - arenaindex: integer index like a column id of current function
        - arenaname: name of the function being benchmarked
        - arenaprefix: string prefix of arenaname
        - arenasuffix: string suffix of arenaname
        - benchfile: filename that contains the current benchmark function
        - benchindex: integer index like a row id of current benchmark
        - benchname: name of the current benchmark function
        - benchstring: string used by timeit to perform the benchmark
        - loops: number of loops used during the benchmark
        - mintime: the minimum benchmark result; i.e., min(times)
        - setupstring: string used by timeit to setup the benchmark
        - times: list of times in seconds of the benchmark results

    Note that when the trial dict is passed to ``trialfilter``, loops,
    mintime, and times will all be None.

    Returns a list of trial dictionaries (described above).
    """
    # Uses: getarenalist, getbenchlist, bettertimeit
    # Used by: BenchRunner, quickstart
    sys.dont_write_bytecode = True
    if verbose is True and trialcallback is None:
        trialcallback = ProgressPrinter(arenadict=arenadict, benchdict=benchdict)
    arenalist = getarenalist(name, arenadict, cython=cython)
    benchlist = getbenchlist(benchdict)

    # create nested dicts of indices {filename: {funcname: index}}
    arenaindices = {}
    for filename, funcnames in arenadict.items():
        d = dict((item, i) for i, item in enumerate(nsorted(funcnames)))
        arenaindices[filename] = d
    benchindices = {}
    for filename, funcnames in benchdict.items():
        d = dict((item, i) for i, item in enumerate(nsorted(funcnames)))
        benchindices[filename] = d

    results = []
    for benchfile, benchname, benchsetup, benchstring in benchlist:
        for arenafile, arenaname, arenasetup in arenalist:
            setupstring = benchsetup + arenasetup
            arenaprefix, arenasuffix = arenaname.split(name, 1)
            trial = dict(
                arenafile=arenafile,
                # should the below "arena*" keys be changed to "func*"?
                arenaindex=arenaindices[arenafile][arenaname],
                arenaname=arenaname,
                arenaprefix=arenaprefix,
                arenasuffix=arenasuffix,
                benchfile=benchfile,
                benchindex=benchindices[benchfile][benchname],
                benchname=benchname,
                benchstring=benchstring,
                loops=None,
                mintime=None,
                setupstring=setupstring,
                times=None,
                # TODO: we plan to add the following:
                # arenafunc=arenafunc,
                # benchargs=benchargs,
                # benchfunc=benchfunc,
                # benchkwargs=benchkwargs,
                # benchoutput=benchoutput,
            )
            # Give the user a chance to skip this benchmark
            if trialfilter is not None and trialfilter(trial) is False:
                continue
            times, loops = bettertimeit(benchstring, setupstring, timer=timer,
                                        mintime=mintime, numrepeat=numrepeat)
            trial.update(
                loops=loops,
                mintime=min(times),
                times=times,
            )
            results.append(trial)
            # Give the user a chance to do something (such as printing output)
            # during the benchmarks.  They can also cancel benchmarking.
            if trialcallback is not None and trialcallback(trial) is False:
                return results
    return results


def quickstart(name, verbose=True, cython=False, mintime=default_mintime,
               numrepeat=default_numrepeat, timer=default_timer, **kwargs):
    """ Convenience command to find, run, and display results of benchmarks.

    Returns results from ``runbenchmarks``.

    Additional keyword arguments may be passed via ``**kwargs``:

        - arenadict: see ``findarenas`` function.
        - arenapaths: see ``findarenas`` function.
        - arenaprefixes: see ``findarenas`` function.
        - benchdict: see ``findbenchmarks`` function.
        - benchpaths: see ``findbenchmarks`` function.
        - benchprefixes: see ``findbenchmarks`` function.
        - dirs: see ``getpaths`` function.
        - sourcedir: see ``getsourcedir`` function.
        - trialcallback: see ``runbenchmarks`` function.
        - trialfilter: see ``runbenchmarks`` function.
    """
    # Uses: getpaths, findarenas, findbenchmarks, runbenchmarks
    class QuickDict(dict):
        def __missing__(self, key):
            return None

        def __getattr__(self, name):
            return self[name]

        def __setattr__(self, name, val):
            self[name] = val

    kwargs = QuickDict(kwargs)
    if kwargs.arenaprefixes is None:
        kwargs.arenaprefixes = default_arenaprefixes
    if kwargs.arenapaths is None:
        kwargs.arenapaths = getpaths(name, sourcedir=kwargs.sourcedir,
                                     prefixes=kwargs.arenaprefixes,
                                     dirs=kwargs.dirs)
    if kwargs.arenadict is None:
        kwargs.arenadict = findarenas(name, prefixes=kwargs.arenaprefixes,
                                      paths=kwargs.arenapaths, cython=cython)

    if kwargs.benchprefixes is None:
        kwargs.benchprefixes = default_benchprefixes
    if kwargs.benchpaths is None:
        kwargs.benchpaths = getpaths(name, sourcedir=kwargs.sourcedir,
                                     prefixes=kwargs.benchprefixes,
                                     dirs=kwargs.dirs)
    if kwargs.benchdict is None:
        kwargs.benchdict = findbenchmarks(name, prefixes=kwargs.benchprefixes,
                                          paths=kwargs.benchpaths)

    results = runbenchmarks(name, kwargs.arenadict, kwargs.benchdict,
                            verbose=verbose, cython=cython,
                            timer=timer, mintime=mintime, numrepeat=numrepeat,
                            trialfilter=kwargs.trialfilter,
                            trialcallback=kwargs.trialcallback)
    if not verbose:
        return results

    arenaprefixes = [prefix + name for prefix in kwargs.arenaprefixes]
    printer = BenchPrinter(results, arenaprefixes=arenaprefixes,
                           benchprefixes=kwargs.benchprefixes)
    resultlist = []
    for (benchfile, arenafile), table in sorted(printer.tables.items()):
        times = printer.to_gfm(table)
        reltimes = printer.to_gfm(table, relative=True)
        rank = printer.to_gfm(table, rank=True)
        resultlist.append((arenafile, benchfile, times, reltimes, rank))

    for arenafile, benchfile, times, reltimes, ranks in resultlist:
        print()
        print('**Benchmarks:** %s' % benchfile)
        print('**Functions:** %s' % arenafile)
        print()
        print('**Time:**')
        print()
        print(times)
        print()
        print('**Relative time:**')
        print()
        print(reltimes)
        print()
        print('**Rank:**')
        print()
        print(rank)

    return results
