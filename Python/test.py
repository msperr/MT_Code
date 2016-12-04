from datetime import datetime, timedelta
import numpy
import util
import storage
from config import config

if __name__ == '__main__2':
    
    a = numpy.int32(2147)
    b = numpy.int32(2148)
    print timedelta(seconds = a)
    print timedelta(seconds = int(b))
    print timedelta(seconds = b)

if __name__ == '__main__2':
    tmp = [1, 2, 3, 2]
    print list(set(i for i in tmp))
    
if __name__ == '__main__2':
    print util.timelist(datetime(2015, 10, 01, 01), datetime(2015, 10, 02, 01), length=4)
    
if __name__ == '__main__':
    filename = config['data']['base'] + 'instance_2.json'
    instance = storage.load_instance_from_json(filename)
    storage.save_instance_to_json(filename, instance, compress=True)
    print 'Finished'

# (1) same __repr__ for different trips