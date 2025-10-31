# Code by durden on Github at https://gist.github.com/durden/0b93cfe4027761e17e69c48f9d5c4118
import sys

def check_sizes(obj, seen=None):
    """Recursively finds size of objects"""

    size = sys.getsizeof(obj)
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0

    # Important mark as seen *before* entering recursion to gracefully handle
    # self-referential objects
    seen.add(obj_id)

    if isinstance(obj, dict):
        size += sum([check_sizes(v, seen) for v in obj.values()])
        size += sum([check_sizes(k, seen) for k in obj.keys()])
    elif hasattr(obj, '__dict__'):
        size += check_sizes(obj.__dict__, seen)
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([check_sizes(i, seen) for i in obj])

    return size