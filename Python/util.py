from itertools import izip_longest

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    args = [iter(iterable)] * n
    return izip_longest(fillvalue=fillvalue, *args)