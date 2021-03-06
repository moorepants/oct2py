"""
.. module:: utils
   :synopsis: Miscellaneous helper constructs

.. moduleauthor:: Steven Silvester <steven.silvester@ieee.org>

"""
import os
import inspect
import dis
import tempfile
import atexit
from oct2py.compat import PY2


def _remove_temp_files():
    """
    Remove the created mat files in the user's temp folder
    """
    import os
    import glob
    import tempfile
    temp = tempfile.NamedTemporaryFile()
    temp.close()
    dirname = os.path.dirname(temp.name)
    for fname in glob.glob(os.path.join(dirname, 'tmp*.mat')):
        try:
            os.remove(fname)
        except OSError:  # pragma: no cover
            pass


atexit.register(_remove_temp_files)


def get_nout():
    """
    Return the number of return values the caller is expecting.

    Adapted from the ompc project.

    Returns
    =======
    out : int
        Number of arguments expected by caller.

    """
    frame = inspect.currentframe()
    # step into the function that called us
    # nout is two frames back
    frame = frame.f_back.f_back
    bytecode = frame.f_code.co_code
    instruction = bytecode[frame.f_lasti + 3]
    instruction = ord(instruction) if PY2 else instruction
    if instruction == dis.opmap['UNPACK_SEQUENCE']:
        howmany = bytecode[frame.f_lasti + 4]
        howmany = ord(howmany) if PY2 else howmany
        return howmany
    elif instruction == dis.opmap['POP_TOP']:
        return 0
    return 1


def create_file():
    """
    Create a MAT file with a random name in the temp directory

    Returns
    =======
    out : str
        Random file name with the desired extension
    """
    temp_file = tempfile.NamedTemporaryFile(suffix='.mat', delete=False)
    temp_file.close()
    return os.path.abspath(temp_file.name)


class Oct2PyError(Exception):
    """ Called when we can't open Octave or Octave throws an error
    """
    pass


class Struct(dict):
    """
    Octave style struct, enhanced.

    Supports dictionary and attribute style access.  Can be pickled,
    and supports code completion in a REPL.

    Examples
    ========
    >>> from oct2py import Struct
    >>> a = Struct()
    >>> a.b = 'spam'  # a["b"] == 'spam'
    >>> a.c["d"] = 'eggs'  # a.c.d == 'eggs'
    >>> print(a)
    {'c': {'d': 'eggs'}, 'b': 'spam'}

    """
    def __getattr__(self, attr):
        """Access the dictionary keys for unknown attributes."""
        try:
            return self[attr]
        except KeyError:
            msg = "'Struct' object has no attribute %s" % attr
            raise AttributeError(msg)

    def __getitem__(self, attr):
        """
        Get a dict value; create a Struct if requesting a Struct member.

        Do not create a key if the attribute starts with an underscore.
        """
        if attr in self.keys() or attr.startswith('_'):
            return dict.__getitem__(self, attr)
        frame = inspect.currentframe()
        # step into the function that called us
        if frame.f_back.f_back and self._is_allowed(frame.f_back.f_back):
            dict.__setitem__(self, attr, Struct())
        elif self._is_allowed(frame.f_back):
            dict.__setitem__(self, attr, Struct())
        return dict.__getitem__(self, attr)
            
    def _is_allowed(self, frame):
        """Check for allowed op code in the calling frame"""
        allowed = [dis.opmap['STORE_ATTR'], dis.opmap['LOAD_CONST'],
                   dis.opmap['STOP_CODE']]
        bytecode = frame.f_code.co_code
        instruction = bytecode[frame.f_lasti + 3]
        instruction = ord(instruction) if PY2 else instruction
        return instruction in allowed

    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

    @property
    def __dict__(self):
        """Allow for code completion in a REPL"""
        return self.copy()


def get_log(name=None):
    """Return a console logger.

    Output may be sent to the logger using the `debug`, `info`, `warning`,
    `error` and `critical` methods.

    Parameters
    ----------
    name : str
        Name of the log.

    References
    ----------
    .. [1] Logging facility for Python,
           http://docs.python.org/library/logging.html

    """
    import logging

    if name is None:
        name = 'oct2py'
    else:
        name = 'oct2py.' + name

    log = logging.getLogger(name)
    log.setLevel(logging.WARN)
    return log


def _setup_log():
    """Configure root logger.

    """
    import logging
    import sys

    try:
        handler = logging.StreamHandler(stream=sys.stdout)
    except TypeError:  # pragma: no cover
        handler = logging.StreamHandler(strm=sys.stdout)

    log = get_log()
    log.addHandler(handler)
    log.setLevel(logging.WARN)
    log.propagate = False

_setup_log()


def _test():  # pragma: no cover
    """Run the doctests for this module
    """
    doctest.testmod()


if __name__ == "__main__":  # pragma: no cover
#    import doctest
    #_test()
    import pickle
    a = Struct()
    a['foo'] = 3
    a['bar'] = 2
    a.baz['bar'] = 1
    a.bob.charlie = 1
    a['fizz']['buzz'] = 3
    a['fizz']['bongo']['bear'] = 4
    #a['fizz']['bongo']
    a['fizz'].dog = 'fido'
    #a['fizz'].yappy
    #a.micro
    #a.baz.dodo
    test = Struct()
    test.spam = 'eggs'
    test.eggs.spam = 'eggs'
    test["foo"]["bar"] = 10
    p = pickle.dumps(test)
    test2 = pickle.loads(p)
