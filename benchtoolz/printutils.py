from __future__ import print_function
import functools
import math
import os
import re
import sys


def best_units(num):
    """ Returns scale factor and prefix such that 1 <= num*scale < 1000"""
    if num < 1e-12:
        return 1e15, 'f'
    if num < 1e-9:
        return 1e12, 'p'
    if num < 1e-6:
        return 1e9, 'n'
    if num < 1e-3:
        return 1e6, 'u'
    if num < 1:
        return 1e3, 'm'
    if num < 1e3:
        return 1.0, ''
    if num < 1e6:
        return 1e-3, 'k'
    if num < 1e9:
        return 1e-6, 'M'
    if num < 1e12:
        return 1e-9, 'G'
    return 1e-12, 'T'


def numericstringkey(sval):
    if isinstance(sval, (tuple, list)):
        return tuple(numericstringkey(x) for x in sval)
    key = []
    for item in re.split(r'(\d+)', sval):
        try:
            key.append(int(item))
        except ValueError:
            key.append(item)
    return tuple(key)


nsorted = functools.partial(sorted, key=numericstringkey)


class ProgressPrinter(object):
    def __init__(self, arenadict=None, benchdict=None, outfile=sys.stdout):
        self.outfile = outfile
        self.print = functools.partial(print, file=outfile)
        self.arenafile = None
        self.benchfile = None
        self.timescale = None
        self.timeunits = None
        if arenadict:
            plural = 's' if len(arenadict) > 1 else ''
            self.print('Using arena file%s:' % plural)
            for arenafile, arenafuncs in nsorted(arenadict.items()):
                self.print('    %s' % arenafile)
                for arenafunc in nsorted(arenafuncs):
                    self.print('        - %s' % arenafunc)
            self.print()
        if benchdict:
            plural = 's' if len(benchdict) > 1 else ''
            self.print('Using benchmark file%s:' % plural)
            for benchfile, benchfuncs in nsorted(benchdict.items()):
                self.print('    %s' % benchfile)
                for benchfunc in nsorted(benchfuncs):
                    self.print('        - %s' % benchfunc)

    def __call__(self, trial):
        benchfile = trial['benchfile']
        benchname = trial['benchname']
        if benchfile != self.benchfile or benchname != self.benchname:
            self.arenafile = None
            self.timescale = None
            self.timeunits = None
            self.benchfile = benchfile
            self.benchname = benchname
            self.print()
            self.print('%s - (%s)' % (benchname, benchfile))
        arenafile = trial['arenafile']
        arenaname = trial['arenaname']
        if arenafile != self.arenafile:
            self.arenafile = arenafile
            self.print('  %s' % arenafile)
        loops = trial['loops']
        mintime = trial['mintime']
        twopow = math.frexp(loops)[1] - 1
        if self.timescale is None:
            self.timescale, self.timeunits = best_units(mintime)
            self.timeunits += 'sec'
        self.print('    %4.3g %s - %s - (2^%d = %d loops)' % (
            mintime * self.timescale, self.timeunits, arenaname, twopow, loops))


# This is very basic and a little hacky.  We should probably try to
# find another package to handle table creation.
class BenchPrinter(object):
    def __init__(self, results, arenaprefixes=None, benchprefixes=None):
        """ Print results in table form

        Keyword arguments:
            - arenaprefixes: list of prefixes to strip from function names
            - benchprefixes: list of prefixes to strip from benchmark names

        The dicts used as table elements have the following items:
            - arenaindex: integer index of the function (i.e., a column id)
            - arenaname: the full name of the function being benchmarked
            - arenashort: name of function with common prefix removed
            - benchindex: integer index of the benchmark (i.e., a row id)
            - benchname: the full name of the benchmark function
            - benchshort: name of benchmark with prefix (e.g., 'bench_') removed
            - isbest: True if function had the best time for this test
            - loops: number of loops used by timeit
            - rank: 1 is the fastest, 2 is the second fasted, etc.
            - reltime: relative time to the best time, reltime = time / besttime
            - scale: scale factor used to change units of time
            - seconds: original data, duration in seconds of benchmark
            - sreltime: string version of `reltime`
            - stime: string version of `time`
            - time: scaled data, time = scale * seconds
            - trialdata: original data dictionary of this trial run
            - units: time units for `time`, such as "ms" for milliseconds
        """
        self.results = results
        self.arenaprefixes = arenaprefixes
        self.benchprefixes = benchprefixes
        self.tables = {}
        # groupby benchfile, arenafile
        self.resultdict = {}
        for trial in results:
            key = (trial['benchfile'], trial['arenafile'])
            if key not in self.resultdict:
                self.resultdict[key] = []
            self.resultdict[key].append(trial)

        for key, trials in self.resultdict.items():
            self.tables[key] = self._build_table(trials)

    def _strip_prefix(self, sval, prefix):
        if prefix is None:
            return sval
        if not isinstance(prefix, list):
            prefix = [prefix]
        # iterate from longest to shortest
        for pre in sorted(prefix, key=len, reverse=True):
            if sval.startswith(pre):
                return sval[len(pre):]
        return sval

    def _build_table(self, trials):
        bybench = {}
        for trial in trials:
            arenaindex = trial['arenaindex']
            arenaname = trial['arenaname']
            arenashort = self._strip_prefix(arenaname, self.arenaprefixes)
            benchindex = trial['benchindex']
            benchname = trial['benchname']
            benchshort = self._strip_prefix(benchname, self.benchprefixes)
            datum = dict(
                arenaindex=arenaindex,
                arenaname=arenaname,
                arenashort=arenashort,
                benchindex=benchindex,
                benchname=benchname,
                benchshort=benchshort,
                loops=trial['loops'],
                seconds=trial['mintime'],
                trialdata=trial,
            )
            if benchindex not in bybench:
                bybench[benchindex] = {}
            bybench[benchindex][arenaindex] = datum

        # Determine units for each test such that the largest value
        # is between 1 and 1000.
        for arenadict in bybench.values():
            sortedvals = sorted(datum['seconds'] for datum in arenadict.values())
            minval = sortedvals[0]
            maxval = sortedvals[-1]
            ranks = dict(zip(sortedvals, range(1, len(sortedvals) + 1)))
            scale, units = best_units(maxval)
            units += 's'
            for datum in arenadict.values():
                seconds = datum['seconds']
                datum.update(
                    isbest=seconds == minval,
                    rank=ranks[seconds],
                    reltime=seconds / minval,
                    scale=scale,
                    time=seconds * scale,
                    units=units,
                )
                datum.update(
                    sreltime='%.3g' % datum['reltime'],
                    stime='%.3g' % datum['time'],
                )
        table = []
        for benchindex, arenadict in sorted(bybench.items()):
            current = []
            table.append(current)
            for arenaindex, datum in sorted(arenadict.items()):
                current.append(datum)
        return table

    # Should we add a keyword to return a 2d table of strings?  Nah, probably not
    def to_gfm(self, table, relative=False, rank=False):
        """ Return a github-flavored markdown table of benchmark results"""
        if relative and rank:
            raise ValueError("'relative' and 'rank' keywords can't both be True")
        data = []
        column_names = ['__Bench__ \\ __Func__ ']
        for datum in table[0]:
            column_names.append(' __%s__ ' % datum['arenashort'])
        data.append(column_names)
        for row in table:
            datum = row[0]
            if relative or rank:
                sval = ' __%s__ ' % datum['benchshort']
            else:
                sval = ' __%s__ (`%s`) ' % (datum['benchshort'], datum['units'])
            crow = [sval]
            data.append(crow)
            for datum in row:
                # set data string and emphasize first and second best
                if relative:
                    val = datum['sreltime']
                elif rank:
                    val = str(datum['rank'])
                else:
                    val = datum['stime']
                if datum['rank'] == 1:
                    sval = ' __%s__ ' % val
                elif datum['rank'] == 2 and len(row) > 2:
                    # Should we actually do this for the second best?
                    sval = ' *%s* ' % val
                else:
                    sval = ' %s ' % val
                crow.append(sval)

        # get max widths
        maxwidths = [0] * len(data[0])
        for row in data:
            for i, sval in enumerate(row):
                maxwidths[i] = max(maxwidths[i], len(sval))

        # center and justify text
        for row in data:
            for i, sval in enumerate(row):
                if i == 0:
                    # right justify row labels
                    row[i] = ' ' * (maxwidths[i] - len(sval)) + sval
                else:
                    row[i] = sval.center(maxwidths[i])

        # add bar below header
        headerbar = []
        for length in maxwidths:
            length = max(0, length - 2)
            headerbar.append(':%s:' % ('-' * length))
        # right justify row/column title (remove leading ':')
        headerbar[0] = ' ' + headerbar[0][1:]
        data.insert(1, headerbar)

        # convert to list of strings, then to a single string
        gfm = []
        for row in data:
            gfm.append('|%s|' % '|'.join(row))
        return os.linesep.join(gfm)
