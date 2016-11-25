from datetime import timedelta
import numpy

if __name__ == '__main__2':
    
    a = numpy.int32(2147)
    b = numpy.int32(2148)
    print timedelta(seconds = a)
    print timedelta(seconds = int(b))
    print timedelta(seconds = b)

if __name__ == '__main__':
    tmp = [1, 2, 3, 2]
    print list(set(i for i in tmp))

# (1) same __repr__ for different trips