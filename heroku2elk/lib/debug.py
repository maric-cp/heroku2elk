
def start_debug(conf):

    if not conf.tornado_debug:

        # noop
        def start_debug(): pass

    else:

        from linecache import getline
        from os import sep
        from random import random
        from tracemalloc import start, Filter, take_snapshot

        from tornado.ioloop import PeriodicCallback, IOLoop

        # wait for tenth this value in seconds before dump statistics
        delay = 60

        def start_debug():

            start()
            cb = PeriodicCallback(record_top(conf.logger), 10 * delay * 10**3)
            cb.start()

        def record_top(logger, key_type='lineno', limit=10):

            def async_sleep():

                def pretty_top():
                    '''see https://docs.python.org/3.5/library/tracemalloc.html#pretty-top
                    Requires python 3.4+.'''
                    kb = 2**10
                    record = logger.info
                    snapshot = take_snapshot()
                    snapshot = snapshot.filter_traces((
                        Filter(False, "<frozen importlib._bootstrap>"),
                        # Filter(False, "<unknown>"),
                    ))
                    top_stats = snapshot.statistics(key_type)

                    record("Top %s lines" % limit)
                    for index, stat in enumerate(top_stats[:limit], 1):
                        frame = stat.traceback[0]
                        # replace "/path/to/module/file.py"
                        # with "module/file.py"
                        filename = sep.join(frame.filename.split(sep)[-2:])
                        record("#%s: %s:%s: %.1f KiB" % (index, filename,
                                                         frame.lineno,
                                                         stat.size / kb))
                        line = getline(frame.filename, frame.lineno).strip()
                        if line:
                            record('    %s' % line)

                    other = top_stats[limit:]
                    if other:
                        size = sum(stat.size for stat in other)
                        record("%s other: %.1f KiB" % (len(other), size / kb))
                    total = sum(stat.size for stat in top_stats)
                    record("Total allocated size: %.1f KiB" % (total / kb))

                return IOLoop.current().call_later(int(random() * delay),
                                                   pretty_top)

            return async_sleep

    return start_debug()
