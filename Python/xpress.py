import itertools
import re

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
            
class parser(object):
    re = None

    def __init__(self, regex):
        self.re = re.compile(regex)

    def parse(self, string, pos=0, progress=None):
        match = self.re.match(string, pos)
        if match:
            value, pos = self.cast(match), match.end()
            return value, pos
        else:
            raise ValueError(pos)

class parser_real(parser):
    re = re.compile(r'(?:\+|-)?(?:\d*\.\d+|\d+\.?\d*)(?:e(?:\+|-)?\d+)?')
    pattern = re.pattern

    def __init__(self):
        pass

    def cast(self, match):
        return float(match.group(0))
            
class parser_string(parser):
    re = re.compile(r'"([^\"\\]*(?:\\.[^\"\\]*)*)"|\'([^\'\\]*(?:\\.[^\'\\]*)*)\'|([A-Za-z_][A-Za-z0-9_]*)')
    pattern = r'"(?:[^\"\\]*(?:\\.[^\"\\]*)*)"|(?:[A-Za-z_][A-Za-z0-9_]*)'

    def __init__(self):
        pass

    def cast(self, match):
        return match.group(1) if match.group(1) != None else (match.group(2) if match.group(2) != None else match.group(3))

class parser_object(parser_string):
    dictionary = None

    def __init__(self, objects, **kwargs):
        self.dictionary = {obj.__xpress_index__(): obj for obj in objects}
        self.dictionary.update(kwargs)

    def cast(self, match):
        index = super(parser_object, self).cast(match)
        if not index in self.dictionary:
            print 'Warning: %s could not be mapped to object.' % index
        return self.dictionary[index] if index in self.dictionary else index#

class parser_index(parser):
    indices = None

    def __init__(self, *args):
        super(parser_index, self).__init__(r'\(\s*{0}\s*\)'.format(r'(?:\s+|\s*,\s*)'.join(r'({0})'.format(index.pattern) for index in args)))
        self.indices = args

    def cast(self, match):
        return tuple(index.parse(group)[0] for index, group in itertools.izip(self.indices, match.groups()))

class parser_pair(object):
    re_delimit = re.compile(r'\s*')
    key = None
    value = None

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def parse(self, string, pos=0, progress=None):

        key, pos = self.key.parse(string, pos, progress)

        match = self.re_delimit.match(string, pos)
        if match:
            pos = match.end()
        else:
            raise ValueError(pos)

        value, pos = self.value.parse(string, pos, progress)
        return (key, value), pos

class parser_collection(object):
    re_open = re.compile(r'\[\s*')
    re_delimit = re.compile(r'\s+|\s*,\s*')
    re_close = re.compile(r'\s*\]')

    value = None
    end = -1

    def __init__(self, value):
        self.value = value

    def parse(self, string, pos=0, progress=None):
        match = self.re_open.match(string, pos)
        if match:
            pos = match.end()
        else:
            raise ValueError(pos)

        while True:
            try:
                item, pos = self.value.parse(string, pos, progress)
                yield item
            except ValueError:
                break

            match = self.re_delimit.match(string, pos)
            if match:
                pos = match.end()
            else:
                break

            if progress:
                progress.update(pos)

        match = self.re_close.match(string, pos)
        if match:
            self.end = match.end()
        else:
            raise ValueError(pos)

class parser_list(parser_collection):

    def __init__(self, value):
        super(parser_list, self).__init__(value)

    def parse(self, string, pos=0, progress=None):
        return list(super(parser_list, self).parse(string, pos, progress)), self.end

class parser_dict(parser_collection):

    def __init__(self, index, value):
        super(parser_dict, self).__init__(parser_pair(parser_index(*index), value))

    def parse(self, string, pos=0, progress=None):
        return dict(((key[0] if len(key) == 1 else key), value) for key, value in super(parser_dict, self).parse(string, pos, progress)), self.end


class parser_tuple(object):
    re_open = re.compile(r'\[\s*')
    re_delimit = re.compile(r'\s+|\s*,\s*')
    re_close = re.compile(r'\s*\]')

    values = None
    end = -1

    def __init__(self, *args):
        self.values = args

    def parse(self, string, pos=0, progress=None):

        items = []

        match = self.re_open.match(string, pos)
        if match:
            pos = match.end()
        else:
            raise ValueError(pos)

        first = True
        for value in self.values:
            if first:
                first = False
            else:
                match = self.re_delimit.match(string, pos)
                if match:
                    pos = match.end()
                else:
                    raise ValueError(pos)

            item, pos = value.parse(string, pos, progress)
            items.append(item)

        match = self.re_close.match(string, pos)
        if match:
            pos = match.end()
        else:
            raise ValueError(pos)

        return tuple(items), pos

class parser_definitions(object):
    re_open = re.compile(r'([A-Za-z_][A-Za-z_0-9]*):\s*')
    re_delimit = re.compile(r'\s+')

    dictionary = None

    def __init__(self, dictionary):
        self.dictionary = dictionary

    def parse(self, string, progress=None):
        
        try:
            result = {}

            pos = 0
            while pos != len(string):
                match = self.re_open.match(string, pos)
                if match:
                    name = match.group(1)
                    if name in self.dictionary:
                        pos = match.end()
                    else:
                        raise ValueError(pos)
                else:
                    raise ValueError(pos)

                result[name], pos = self.dictionary[name].parse(string, pos, progress)

                match = self.re_delimit.match(string, pos)
                if match:
                    pos = match.end()
                else:
                    break

                if progress:
                    progress.update(pos)

            if pos != len(string):
                raise ValueError(pos)

            return result

        except (ValueError, StopIteration) as e:
            value = e.args[0]
            last = string.rfind('\n', 0, value)
            raise ValueError('Parsing error occured at {0}, {1}'.format(string.count('\n', 0, last + 1) + 1, value - last))
        
def write(f, ordereddict):
    for name, value in ordereddict.iteritems():
        f.write(name)
        f.write(': ')
        write_value(f, value)
        f.write("\n")

def write_value(f, obj):
    if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, bool):
        f.write(repr(obj))
    elif isinstance(obj, str) or isinstance(obj, unicode):
        f.write('"')
        f.write(obj)
        f.write('"')
    elif isinstance(obj, set) or isinstance(obj, list) or isinstance(obj, tuple):
        f.write('[')
        first = True
        for item in obj:
            if first:
                first = False
            else:
                f.write(' ')
            write_value(f, item)
        f.write(']')
    elif isinstance(obj, dict):
        f.write('[')
        for index, value in obj.iteritems():
            f.write('\n\t(')
            write_index(f, index, True)
            f.write(') ')
            write_value(f, value)
        f.write('\n]')
    elif hasattr(obj, 'next'):
        first = next(obj, None)
        if isinstance(first, tuple):
            f.write('[')
            f.write('\n\t(')
            index, value = first
            write_index(f, index, True)
            f.write(') ')
            write_value(f, value)
            for index, value in obj:
                f.write('\n\t(')
                write_index(f, index, True)
                f.write(') ')
                write_value(f, value)
            f.write('\n]')
        elif first <> None:
            f.write('[')
            write_value(f, first)
            for item in obj:
                f.write(' ')
                write_value(f, item)
            f.write(']')
        else:
            f.write('[]')
    elif hasattr(obj, '__index__'):
        write_value(f, obj.__index__())
    elif obj is None:
        f.write("''")
    else:
        write_value(f, repr(obj))

def write_index(f, obj, stringify=False):
    if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, bool):
        f.write(repr(obj))
    elif isinstance(obj, str) or isinstance(obj, unicode):
        f.write('"')
        f.write(obj)
        f.write('"')
    elif hasattr(obj, '__iter__'):
        it = iter(obj)
        write_index(f, it.next(), stringify=stringify)
        for item in it:
            f.write(' ')
            write_index(f, item, stringify=stringify)
    else:
        if stringify:
            write_index(f, obj.__index__())
        else:
            f.write(obj.__index__())