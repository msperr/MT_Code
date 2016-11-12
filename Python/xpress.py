def xpress_index(obj, stringify=False):
    if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, bool):
        return repr(obj)
    elif isinstance(obj, str) or isinstance(obj, unicode):
        return '"%s"' % obj if stringify else str(obj)
    elif hasattr(obj, '__iter__'):
        return ' '.join(xpress_index(item, stringify=stringify) for item in obj)
    else:
        return xpress_index(str(obj.__xpress_index__())) if stringify else str(obj.__xpress_index__())

def xpress_value(obj):
    if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, bool):
        return repr(obj)
    elif isinstance(obj, str) or isinstance(obj, unicode):
        return '"%s"' % obj
    elif isinstance(obj, set) or isinstance(obj, list):
        return '[%s]' % ' '.join(xpress_value(item) for item in obj)
    elif isinstance(obj, dict):
        return '[%s]' % ' '.join(('(%s) %s' % (xpress_index(index, True), xpress_value(value))) for index, value in obj.iteritems())
    else:
        return repr(obj)

def xpress_data_string(ordereddict):
    return "\n".join(('%s: %s' % (name, xpress_value(value))) for name, value in ordereddict.iteritems())







def xpress_write(f, ordereddict):
    for name, value in ordereddict.iteritems():
        f.write(name)
        f.write(': ')
        xpress_write_value(f, value)
        f.write("\n")

def xpress_write_value(f, obj):
    if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, bool):
        f.write(repr(obj))
    elif isinstance(obj, str) or isinstance(obj, unicode):
        f.write('"')
        f.write(obj)
        f.write('"')
    elif isinstance(obj, set) or isinstance(obj, list):
        return xpress_write_value(f, iter(obj))
    elif isinstance(obj, dict):
        return xpress_write_value(f, obj.iteritems())
    elif hasattr(obj, 'next'):
        first = next(obj, None)
        if isinstance(first, tuple):
            f.write('[')
            f.write('\n\t(')
            index, value = first
            xpress_write_index(f, index, True)
            f.write(') ')
            xpress_write_value(f, value)
            for index, value in obj:
                f.write('\n\t(')
                xpress_write_index(f, index, True)
                f.write(') ')
                xpress_write_value(f, value)
            f.write('\n]')
        elif first <> None:
            f.write('[')
            xpress_write_value(f, first)
            for item in obj:
                f.write(' ')
                xpress_write_value(f, item)
            f.write(']')
        else:
            f.write('[]')
    else:
        f.write(repr(obj))

def xpress_write_index(f, obj, stringify=False):
    if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, bool):
        f.write(repr(obj))
    elif isinstance(obj, str) or isinstance(obj, unicode):
        f.write('"')
        f.write(obj)
        f.write('"')
    elif hasattr(obj, '__iter__'):
        it = iter(obj)
        xpress_write_index(f, it.next(), stringify=stringify)
        for item in it:
            f.write(' ')
            xpress_write_index(f, item, stringify=stringify)
    else:
        if stringify:
            xpress_write_index(f, obj.__xpress_index__())
        else:
            f.write(obj.__xpress_index__())


def get_dict(points):
    dictionary = dict()
    for point in points:
        dictionary[xpress_index(point)] = point
    return dictionary