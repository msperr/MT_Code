from datetime import datetime, timedelta
import numpy
import util

if __name__ == '__main__2':
    
    a = numpy.int32(2147)
    b = numpy.int32(2148)
    print timedelta(seconds = a)
    print timedelta(seconds = int(b))
    print timedelta(seconds = b)

if __name__ == '__main__2':
    tmp = [1, 2, 3, 2]
    print list(set(i for i in tmp))
    
if __name__ == '__main__':
    print util.timelist(datetime(2015, 10, 01, 01), datetime(2015, 10, 02, 01), length=4)

# (1) same __repr__ for different trips