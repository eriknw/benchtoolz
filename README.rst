BenchToolz
==========

``benchtoolz`` allows convenient and powerful benchmarking of Python
and Cython code.  It aims to be the benchmarking tool you always wish
you had or never knew you wanted.  It is still in **alpha** stage of
development, and *you* can `help make it better <https://github.com/eriknw/benchtoolz/issues>`__!

The goal of benchmarking it to compare the *relative* performance of a
set of operations.  Benchmarking is typically used to develop a faster
implementation of a function, and to track relative performance of a
function over time, which, when automated, can easily identify
performance improvements and regressions.

``benchtoolz`` makes it easy to run the same benchmarks on several
competing implementations of a function, and to view (and share) the
results side-by-side thus making it easy to compare results.
Tracking benchmark performance over time (such as for each commit in
a source repository) is not yet supported, but we may leverage
projects such as `vbench <https://github.com/pydata/vbench>`__ or
`airspeed velocity (asv) <https://github.com/spacetelescope/asv>`__
to achieve this task as painlessly as possible.

Example
-------

Let's consider a simple and contrived example: we want a function named
``zeros`` that returns a list containing ``n`` number of zeros.  First
we define competing implementations in the file
"example_benchmarks/zeros.py":

.. code:: python

    from itertools import repeat

    def zeros_imul(n):
        l = [0]
        l *= n
        return l

    def zeros_mul(n):
        return n * [0]

    def zeros_repeat(n):
        return list(repeat(0, n))

    def zeros_slow(n):
        return [0 for _ in range(n)]

Next we define the benchmarks to run on all variations of ``zeros``
in the file "example_benchmarks/bench_zeros.py":

.. code:: python

    def bench_empty():
        zeros(0)

    def bench_small():
        zeros(10)

    def bench_large():
        zeros(10000)

Although we don't yet have a command line utility to easily run
benchmarks (see `issue ## <https://github.com/eriknw/benchtoolz/issues>`__,
a simple Python script (let's call it "runexample.py") gets the job done:

.. code:: python

    if __name__ == '__main__':
        from benchtoolz import quickstart
        quickstart('zeros')

This prints the results in real-time as the benchmarks are running,
and summary tables are printed at the very end.  By default, the
summary tables are formatted as github-flavored markdown (gfm) tables,
which are cleanly formatted ASCII that can be copy/pasted to github
to create tables such as the following:

**Time:**

=====================  ========  =========  ==========  ========
**Bench** \\ **Func**  **imul**   **mul**   **repeat**  **slow**
---------------------  --------  ---------  ----------  --------
     **empty** (*us*)   *0.549*  **0.521**      1.8       0.654
     **large** (*us*)   **102**    *108*        134        905
     **small** (*us*)   *0.774*  **0.737**     2.13       1.93
=====================  ========  =========  ==========  ========

**Relative time:**

=====================  ========  =======  ==========  ========
**Bench** \\ **Func**  **imul**  **mul**  **repeat**  **slow**
---------------------  --------  -------  ----------  --------
            **empty**   *1.05*    **1**      3.46       1.26
            **large**   **1**     *1.06*     1.31       8.87
            **small**   *1.05*    **1**      2.89       2.62
=====================  ========  =======  ==========  ========

**Rank:**

=====================  ========  =======  ==========  ========
**Bench** \\ **Func**  **imul**  **mul**  **repeat**  **slow**
---------------------  --------  -------  ----------  --------
            **empty**     *2*     **1**        4          3
            **large**    **1**     *2*         3          4
            **small**     *2*     **1**        4          3
=====================  ========  =======  ==========  ========

As we can see, ``zeros_mul`` is the fastest variant for small lists,
``zeros_imul`` is the fastest for large lists, and there is only about
a 5-6% difference in performance between these two functions.
``zeros_repeat`` and ``zeros_slow`` perform poorly.

We should remark that micro-benchmarks such as the given example are
not always useful for speeding up your application.  It is up to you
to decide what is worth tweaking and benchmarking.  At the very least,
such excercises can often be educational.  Finally, keep in mind that
members of the Python community typically favor code that is easy to
understand.

Features
--------

**Write benchmarks as naturally as possible:**

- Each benchmark is a regular Python function
- Setup occurs in the global scope of the benchmark file
- Compare this to ``timeit`` for which *strings* are used as
  benchmark code and setup
- Benchmark files and functions are identified by common prefixes
  ("bench_" by default)

**Prefer convention over configuration:**

- The following illustrates typical usage for benchmarking a function
  named ``myfunc``

  - Following these conventions makes using ``benchtoolz`` a breeze
  - You are not forced to use these conventions if you don't like them

- Variants of function ``myfunc`` are defined in the file "myfunc.py"
  ("myfunc.pyx" for Cython)
- The variants are distinguished by their suffix, such as ``myfunc_prev``
- Benchmarks are defined in the file "bench_myfunc.py"
- There may be multiple variant files and benchmark files for ``myfunc``
  contained in multiple directories

  - By default, ``benchtoolz`` searches in directories "\*benchmark\*"

- All benchmarks are run on each variant of ``myfunc`` (even those from
  separate directories)

**Run single benchmark with multiple data:**

- *This is not yet implemented!*
- It is very common for benchmarks to be identical except for the input
  data; in this case, a single benchmark function may be defined that
  will automatically run multiple times using different data
- There are two ways to define a benchmark to use multiple input data:

  1. Define a positional argument; the name of the argument identifies
     the prefix of the data to use
  2. Define a keyword argument with a list or dict of values; the
     values will be used as the input data

- For example, this can be applied to the ``zeros`` example above

  - The original code:


    .. code:: python

        def bench_empty():
            zeros(0)

        def bench_small():
            zeros(10)

        def bench_large():
            zeros(10000)


  - Can be replaced with:


    .. code:: python

        data_empty = 0
        data_small = 10
        data_large = 10000

        def bench(data):
            zeros(data)


  - Or:


    .. code:: python

        def bench(data=[0, 10, 10000]):
            zeros(data)


  - And we may allow the following to give names to the data:


    .. code:: python

        def bench(data={'empty': 0, 'small': 10, 'large': 10000}):
            zeros(data)


**Benchmark Cython functions:**

- The Cython language is a superset of the Python language that combines
  elements of C to increase performance

  - Cython generates C code from Cython code that is then statically compiled
  - It is a very easy way to write fast C extensions usable in CPython
  - Cython is commonly used to speed up performance-critical sections of code
  - Hence, if you are benchmarking a function to optimize it, why not
    try writing it in Cython?

- ``benchtoolz`` automatically compiles Cython files via ``pyximport``

  - If necessary, build dependencies may be defined in `"\*.pyxdep"
    files <http://docs.cython.org/src/userguide/source_files_and_compilation.html#dependency-handling>`__
  - For even more control, build via ``distutils`` in "setup.py" as done
    for typical Cython projects (*not yet implemented*)

**Benchmarks run quickly:**

- Even though benchmarks are written as functions, benchmarks are
  run *without* the overhead of a function call
- A suitable number of loop iterations is adaptively and efficiently
  determined until the runtime of the benchmark is greater than
  ``mintime`` (default 0.25 seconds)
- Unlike ``timeit`` and IPython's ``%timeit`` magic, the number of loops
  is a power of two, not 10

  - Benchmarks that have similar performance will use similar numbers
    of loops
  - The time of each benchmark will typically be between ``mintime``
    and ``2 * mintime`` (if powers of 10 were used, the time would be
    between ``mintime`` and ``10 * mintime``)

- ``timeit`` is used under the covers, which avoids a number of common
  traps for measuring execution times

**Benchmarks are testable:**

- Benchmark functions may return a value (must be the last statement)
- It is good practice to include a *reference* implementation of the
  function being benchmarked in the benchmark file, which enables
  two things:

  1. Benchmark behavior may be tested using standard testing frameworks
  2. The output from using each variant being benchmarked will be
     checked for consistency (*not yet implemented*)


**Users have fine control over what Python code gets imported and executed:**

- No external Python modules are imported (hence, executed) when
  *searching* for benchmarks and functions to benchmark
- The user can review and modify the list of filenames and functions
  that will be used *after* they are found but *before* they are imported
- For the extremely paranoid, it is possible to simply provide an explicit
  list of filenames and function names to use thereby avoiding the search
  phase altogether
- The user can provide a callback function that executes after benchmark
  files are imported but before each benchmark is run

  - The callback function receives a modifiable ``dict`` that contains all the
    information for the current benchmark being run
  - For example, this allows a user to check for and take action on
    an attribute that was added to a function such as ``myfunc.runbench = False``
  - If the callback function returns ``False``, the current benchmark is skipped


Why?
----

``benchtoolz`` is the package I wish I had when I first developed `cytoolz,
<https://github.com/pytoolz/cytoolz>`__ which reimplementes `toolz
<https://github.com/pytoolz/cytoolz>`__ in Cython.  ``toolz`` and ``cytoolz``
implement a collection of high-performance utilities for functions, dicts,
and iterables, and we care about the performance of each function.  We will
use ``benchtoolz`` as we continue to develop and optimize ``toolz`` and
``cytoolz`` (TODO: link to the PyToolz benchmark repository once it is
created).

``benchtoolz`` will also allow clearer communication of benchmark results,
and make these benchmarks more reproducible.  When discussing performance
in github issues, I find we often copy/paste output from an IPython
session that uses the ``%timeit`` magic.  This is often a long wall of
text that is difficult to comprehend.  ``benchtoolz`` outputs tables of
results that can be copy/pasted to github.  These are rendered as tables
and are very easy to understand.

LICENSE
-------

New BSD. See `License File <https://github.com/eriknw/benchtoolz/blob/master/LICENSE.txt>`__.

Install
-------

``benchtoolz`` is not yet in the Python Package Index (PyPI).  You must
install it manually such as:

::

    python setup.py install

Dependencies
------------

Cython is only required if Cython functions are being benchmarked,
and ``benchtoolz`` has no other external dependencies.
``benchtoolz`` has only been used with Python 2.7, but we plan to
support Python 2.6+ and Python 3.2+.

Contributions Welcome
---------------------

``benchtoolz`` aims to be a benchmarking tool that is easy to use yet
is very powerful.  Contributions are welcome and attribution will
*always* be given.  If ``benchtoolz`` doesn't match your desired
workflow, we will probably accept contributions that make it work
well for *you*.

Please take a look at our
`issue page <https://github.com/eriknw/benchtoolz/issues>`__
for contribution ideas.

