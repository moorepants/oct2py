"""
py2oct_test - Test value passing between python and Octave.

Known limitations
-----------------
* Nested lists with strings in them cannot be sent to Octave. This applies to
Numpy arrays of rank > 1 that are string or unicode as well.  Also, lists
cannot contain mixed type (strings and sublists for example).
I will try and figure this out for future releases.

* The following Numpy array types cannot be sent directly via an HDF.  The
float96 and complex192 can be recast as float64 and complex128.
   ** float96('g')
   ** complex192('G')
   ** object('o')
   ** read-write buffer('V')

* Sparse and empty matrices have not yet been implemented or tested.

"""
import unittest
import os
import sys
import numpy as np

sys.path.append(os.path.abspath('../..'))

try:
    from oct2py._oct2py import Oct2Py, Oct2PyError
    from oct2py._utils import Struct, _remove_files
except (ValueError, ImportError):
    from .._oct2py import Oct2Py, Oct2PyError
    from .._utils import Struct, _remove_files

octave = Oct2Py()
octave.addpath(os.path.dirname(__file__))

if sys.version_info[0] == 3:
    unicode = str
    long = int

TYPE_CONVERSIONS = [(int, 'int32', np.int32),
                (long, 'int64', np.int64),
                (float, 'double', np.float64),
                (complex, 'double', np.complex128),
                (str, 'char', unicode),
                (unicode, 'cell', unicode),
                (bool, 'int8', np.int8),
                (None, 'double', np.float64),
                (dict, 'struct', Struct),
                (np.int8, 'int8', np.int8),
                (np.int16, 'int16', np.int16),
                (np.int32, 'int32', np.int32),
                (np.int64, 'int64', np.int64),
                (np.uint8, 'uint8', np.uint8),
                (np.uint16, 'uint16', np.uint16),
                (np.uint32, 'uint32', np.uint32),
                (np.uint64, 'uint64', np.uint64),
                #(np.float16, 'double', np.float64),
                (np.float32, 'double', np.float64),
                (np.float64, 'double', np.float64),
                (np.str, 'char', np.unicode),
                (np.double, 'double', np.float64),
                (np.complex64, 'double', np.complex128),
                (np.complex128, 'double', np.complex128), ]


class TypeConversions(unittest.TestCase):
    """Test roundtrip datatypes starting from Python
    """

    def test_python_conversions(self):
        """Test roundtrip python type conversions
        """
        for out_type, oct_type, in_type in TYPE_CONVERSIONS:
            if out_type == dict:
                outgoing = dict(x=1)
            elif out_type == None:
                outgoing = None
            else:
                outgoing = out_type(1)
            incoming, octave_type = octave.roundtrip(outgoing)
            try:
                self.assertEqual(octave_type, oct_type)
            except AssertionError:
                if octave_type == 'int32' and oct_type == 'int64':
                    pass
                elif octave_type == 'char' and oct_type == 'cell':
                    pass
                else:
                    raise
            try:
                self.assertEqual(type(incoming), in_type)
            except AssertionError:
                if type(incoming) == np.int32 and in_type == np.int64:
                    pass
                else:
                    assert in_type(incoming) == incoming


class IncomingTest(unittest.TestCase):
    """Test the importing of all Octave data types, checking their type

    Uses test_datatypes.m to read in a dictionary with all Octave types
    Tests the types of all the values to make sure they were
        brought in properly.

    """
    def setUp(self):
        """Open an instance of Octave and get a struct with all datatypes.
        """
        self.data = octave.test_datatypes()

    def tearDown(self):
        _remove_files()

    def helper(self, base, keys, types):
        """
        Perform type checking of the values

        Parameters
        ==========
        base : dict
            Sub-dictionary we are accessing.
        keys : array-like
            List of keys to test in base.
        types : array-like
            List of expected return types for the keys.

        """
        for key, type_ in zip(keys, types):
            try:
                self.assertEqual(type(base[key]), type_)
            except AssertionError:
                assert type_(base[key]) == base[key]

    def test_int(self):
        """Test incoming integer types
        """
        keys = ['int8', 'int16', 'int32', 'int64',
                    'uint8', 'uint16', 'uint32', 'uint64']
        types = [np.int8, np.int16, np.int32, np.int64,
                    np.uint8, np.uint16, np.uint32, np.uint64]
        self.helper(self.data.num.int, keys, types)

    def test_floats(self):
        """Test incoming float types
        """
        keys = ['float32', 'float64', 'complex', 'complex_matrix']
        types = [np.float64, np.float64, np.complex128, np.ndarray]
        self.helper(self.data.num, keys, types)
        self.assertEqual(self.data.num.complex_matrix.dtype,
                         np.dtype('complex128'))

    def test_misc_num(self):
        """Test incoming misc numeric types
        """
        keys = ['inf', 'NaN', 'matrix', 'vector', 'column_vector', 'matrix3d',
                'matrix5d']
        types = [np.float64, np.float64, np.ndarray, np.ndarray, np.ndarray,
                 np.ndarray, np.ndarray]
        self.helper(self.data.num, keys, types)

    def test_logical(self):
        """Test incoming logical type
        """
        self.assertEqual(type(self.data.logical), np.ndarray)

    def test_string(self):
        """Test incoming string types
        """
        keys = ['basic', 'char_array', 'cell_array']
        types = [unicode, list, list]
        self.helper(self.data.string, keys, types)

    def test_struct(self):
        ''' Test incoming struct types '''
        keys = ['name', 'age']
        types = [list, list]
        self.helper(self.data.struct.array, keys, types)

    def test_cell_array(self):
        ''' Test incoming cell array types '''
        keys = ['vector', 'matrix']
        types = [list, list]
        self.helper(self.data.cell, keys, types)


class RoundtripTest(unittest.TestCase):
    """Test roundtrip value and type preservation between Python and Octave.

    Uses test_datatypes.m to read in a dictionary with all Octave types
    uses roundtrip.m to send each of the values out and back,
        making sure the value and the type are preserved.

    """
    def setUp(self):
        """Open an instance of Octave and get a struct all datatypes.
        """
        self.data = octave.test_datatypes()

    def nested_equal(self, val1, val2):
        """Test for equality in a nested list or ndarray
        """
        if isinstance(val1, list):
            for (subval1, subval2) in zip(val1, val2):
                if isinstance(subval1, list):
                    self.nested_equal(subval1, subval2)
                elif isinstance(subval1, np.ndarray):
                    np.allclose(subval1, subval2)
                else:
                    self.assertEqual(subval1, subval2)
        elif isinstance(val1, np.ndarray):
            np.allclose(val1, np.array(val2))
        elif isinstance(val1, basestring):
            self.assertEqual(val1, val2)
        elif np.alltrue(np.isnan(val1)) and np.alltrue(np.isnan(val2)):
            pass
        else:
            self.assertEqual(val1, val2)

    def helper(self, outgoing, expected_type=None):
        """
        Use roundtrip.m to make sure the data goes out and back intact.

        Parameters
        ==========
        outgoing : object
            Object to send to Octave.

        """
        incoming = octave.roundtrip(outgoing)
        if expected_type is None:
            expected_type = type(outgoing)
        try:
            self.nested_equal(incoming, outgoing)
        except AssertionError:
            # need to test for NaN explicitly
            try:
                if not (np.isnan(outgoing) and np.isnan(incoming)):
                    raise
            except (NotImplementedError, TypeError):
                raise
        self.assertEqual(type(incoming), expected_type)

    def test_int(self):
        """Test roundtrip value and type preservation for integer types
        """
        for key in ['int8', 'int16', 'int32', 'int64',
                    'uint8', 'uint16', 'uint32', 'uint64']:
            self.helper(self.data.num.int[key])

    def test_float(self):
        """Test roundtrip value and type preservation for float types
        """
        for key in ['float64', 'complex', 'complex_matrix']:
            self.helper(self.data.num[key])
        self.helper(self.data.num['float32'], np.float64)

    def test_misc_num(self):
        """Test roundtrip value and type preservation for misc numeric types
        """
        for key in ['inf', 'NaN', 'matrix', 'vector', 'column_vector',
                    'matrix3d', 'matrix5d']:
            self.helper(self.data.num[key])

    def test_logical(self):
        """Test roundtrip value and type preservation for logical type
        """
        self.helper(self.data.logical)

    def test_string(self):
        """Test roundtrip value and type preservation for string types
        """
        for key in ['basic', 'cell_array']:
            self.helper(self.data.string[key])

    def test_struct(self):
        """Test roundtrip value and type preservation for struct types
        """
        self.helper(self.data.struct.array['name'])
        self.helper(self.data.struct.array['age'], np.ndarray)

    def test_cell_array(self):
        """Test roundtrip value and type preservation for cell array types
        """
        for key in ['vector', 'matrix']:
            self.helper(self.data.cell[key])


class BuiltinsTest(unittest.TestCase):
    """Test the exporting of standard Python data types, checking their type.

    Runs roundtrip.m and tests the types of all the values to make sure they
    were brought in properly.

    """
    def helper(self, outgoing, incoming=None, expected_type=None):
        """
        Uses roundtrip.m to make sure the data goes out and back intact.

        Parameters
        ==========
        outgoing : object
            Object to send to Octave
        incoming : object, optional
            Object already retreived from Octave

        """
        if incoming is None:
            try:
                incoming = octave.roundtrip(outgoing)
            except Oct2PyError:
                raise
        if not expected_type:
            for out_type, _, in_type in TYPE_CONVERSIONS:
                if out_type == type(outgoing):
                    expected_type = in_type
                    break
        if not expected_type:
            expected_type = np.ndarray
        try:
            self.assertEqual(incoming, outgoing)
        except ValueError:
            assert np.allclose(np.array(incoming), np.array(outgoing))
        try:
            self.assertEqual(type(incoming), expected_type)
        except AssertionError:
            assert expected_type(incoming) == incoming

    def test_dict(self):
        """Test python dictionary
        """
        test = dict(x='spam', y=[1, 2, 3])
        incoming = octave.roundtrip(test)
        #incoming = dict(incoming)
        for key in incoming:
            self.helper(test[key], incoming[key])

    def test_nested_dict(self):
        """Test nested python dictionary
        """
        test = dict(x=dict(y=1e3, z=[1, 2]), y='spam')
        incoming = octave.roundtrip(test)
        incoming = dict(incoming)
        for key in test:
            if isinstance(test[key], dict):
                for subkey in test[key]:
                    self.helper(test[key][subkey], incoming[key][subkey])
            else:
                self.helper(test[key], incoming[key])

    def test_set(self):
        """Test python set type
        """
        test = set((1, 2, 3, 3))
        incoming = octave.roundtrip(test)
        assert np.allclose(tuple(test), incoming)
        self.assertEqual(type(incoming), np.ndarray)

    def test_tuple(self):
        """Test python tuple type
        """
        test = tuple((1, 2, 3))
        self.helper(test, expected_type=np.ndarray)

    def test_list(self):
        """Test python list type
        """
        tests = [[1, 2], ['a', 'b']]
        self.helper(tests[0])
        self.helper(tests[1], expected_type=list)

    def test_list_of_tuples(self):
        """Test python list of tuples
        """
        test = [(1, 2), (1.5, 3.2)]
        self.helper(test)

    def test_numeric(self):
        """Test python numeric types
        """
        test = np.random.randint(1000)
        self.helper(int(test))
        self.helper(long(test))
        self.helper(float(test))
        self.helper(complex(1, 2))

    def test_string(self):
        """Test python str and unicode types
        """
        tests = ['spam', unicode('eggs')]
        for test in tests:
            self.helper(test)

    def test_nested_list(self):
        """Test python nested lists
        """
        test = [['spam', 'eggs'], ['foo ', 'bar ']]
        self.helper(test, expected_type=list)
        test = [[1, 2], [3, 4]]
        self.helper(test)
        test = [[1, 2], [3, 4, 5]]
        incoming = octave.roundtrip(test)
        for i in range(len(test)):
            assert np.alltrue(incoming[i] == np.array(test[i]))

    def test_bool(self):
        """Test boolean values
        """
        tests = (True, False)
        for test in tests:
            incoming = octave.roundtrip(test)
            self.assertEqual(incoming, test)
            self.assertEqual(incoming.dtype, np.dtype('int8'))

    def test_none(self):
        """Test sending None type
        """
        incoming = octave.roundtrip(None)
        assert np.isnan(incoming)


class NumpyTest(unittest.TestCase):
    """Check value and type preservation of Numpy arrays
    """
    def setUp(self):
        """Create the numpy code types to check and blacklist some.
        """
        self.codes = np.typecodes['All']
        self.blacklist = 'gGV'

    def test_scalars(self):
        """Send a scalar numpy type and make sure we get the same number back.
        """
        for typecode in self.codes:

            outgoing = (np.random.randint(-255, 255) + np.random.rand(1))
            try:
                outgoing = outgoing.astype(typecode)
            except TypeError:
                continue
            if typecode in self.blacklist:
                self.assertRaises(Oct2PyError, octave.roundtrip, outgoing)
                continue
            incoming = octave.roundtrip(outgoing)
            if outgoing.dtype.str in ['<M8[us]', '<m8[us]']:
                outgoing = outgoing.astype(np.uint64)
            try:
                assert np.allclose(incoming, outgoing)
            except (ValueError, TypeError, NotImplementedError,
                     AssertionError):
                assert np.alltrue(np.array(incoming).astype(typecode) ==
                                   outgoing)

    def test_ndarrays(self):
        """Send an ndarray and make sure we get the same array back
        """
        for typecode in self.codes:
            ndims = np.random.randint(2, 4)
            size = [np.random.randint(1, 10) for i in range(ndims)]
            outgoing = (np.random.randint(-255, 255, tuple(size)))
            outgoing += np.random.rand(*size)
            if typecode in ['U', 'S']:
                outgoing = [[['spam', 'eggs'], ['spam', 'eggs']],
                            [['spam', 'eggs'], ['spam', 'eggs']]]
                outgoing = np.array(outgoing).astype(typecode)
            else:
                try:
                    outgoing = outgoing.astype(typecode)
                except TypeError:
                    continue
            if typecode in self.blacklist:
                self.assertRaises(Oct2PyError, octave.roundtrip, outgoing)
                continue
            incoming = octave.roundtrip(outgoing)
            incoming = np.array(incoming)
            if 1 in outgoing.shape:
                if outgoing.shape[1] == 1 and len(outgoing.shape) == 2:
                    pass
                else:
                    outgoing = outgoing.squeeze()
            if outgoing.dtype.str in ['<M8[us]', '<m8[us]']:
                outgoing = outgoing.astype(np.uint64)
            try:
                assert np.allclose(incoming, outgoing)
            except (AssertionError, ValueError, TypeError,
                     NotImplementedError):
                assert np.alltrue(np.array(incoming).astype(typecode).squeeze()
                                   == outgoing)


class BasicUsageTest(unittest.TestCase):
    """Excercise the basic interface of the package
    """
    def test_run(self):
        """Test the run command
        """
        out = octave.run('y=ones(3,3)')
        desired = """y =

        1        1        1
        1        1        1
        1        1        1
"""
        self.assertEqual(out, desired)
        out = octave.run('x = mean([[1, 2], [3, 4]])', verbose=True)
        self.assertEqual(out, 'x =  2.5000')
        self.assertRaises(Oct2PyError, octave.run, '_spam')

    def test_call(self):
        """Test the call command
        """
        out = octave.call('ones', 1, 2)
        assert np.allclose(out, np.ones((1, 2)))
        U, S, V = octave.call('svd', [[1, 2], [1, 3]])
        assert np.allclose(U, ([[-0.57604844, -0.81741556],
                            [-0.81741556, 0.57604844]]))
        assert np.allclose(S,  ([[3.86432845, 0.],
                             [0., 0.25877718]]))
        assert np.allclose(V,  ([[-0.36059668, -0.93272184],
         [-0.93272184, 0.36059668]]))
        out = octave.call('roundtrip.m', 1)
        self.assertEqual(out, 1)
        fname = os.path.join(__file__, 'roundtrip.m')
        out = octave.call(fname, 1)
        self.assertEqual(out, 1)
        self.assertRaises(Oct2PyError, octave.call, '_spam')

    def test_put_get(self):
        """Test putting and getting values
        """
        octave.put('spam', [1, 2])
        out = octave.get('spam')
        try:
            assert np.allclose(out, np.array([1, 2]))
        except AssertionError:
            raise
        octave.put(['spam', 'eggs'], ['foo', [1, 2, 3, 4]])
        spam, eggs = octave.get(['spam', 'eggs'])
        self.assertEqual(spam, 'foo')
        assert np.allclose(eggs, np.array([[1, 2, 3, 4]]))
        self.assertRaises(Oct2PyError, octave.put, '_spam', 1)
        self.assertRaises(Oct2PyError, octave.get, '_spam')

    def test_help(self):
        """Testing help command
        """
        out = octave.cos.__doc__
        try:
            self.assertEqual(out[:5], '\n`cos')
        except AssertionError:
            self.assertEqual(out[:5], '\ncos ')

    def test_dynamic(self):
        """Test the creation of a dynamic function
        """
        tests = [octave.zeros, octave.ones, octave.plot]
        for test in tests:
            try:
                self.assertEqual(repr(type(test)), "<type 'function'>")
            except AssertionError:
                self.assertEqual(repr(type(test)), "<class 'function'>")
        self.assertRaises(Oct2PyError, octave.__getattr__, 'aaldkfasd')
        self.assertRaises(Oct2PyError, octave.__getattr__, '_foo')
        self.assertRaises(Oct2PyError, octave.__getattr__, 'foo\W')

    def test_open_close(self):
        """Test opening and closing the Octave session
        """
        oct_ = Oct2Py()
        oct_.close()
        self.assertRaises(Oct2PyError, oct_.put, names=['a'],
                          var=[1.0])

    def test_struct(self):
        """Test Struct construct
        """
        test = Struct()
        test.spam = 'eggs'
        test.eggs.spam = 'eggs'
        self.assertEqual(test['spam'], 'eggs')
        self.assertEqual(test['eggs']['spam'], 'eggs')

    def test_syntax_error(self):
        """Make sure a syntax error in Octave throws an Oct2PyError
        """
        oct_ = Oct2Py()
        self.assertRaises(Oct2PyError, oct_.eval, cmds="a='1")


if __name__ == '__main__':
    print('oct2py test')
    print('*' * 20)
    unittest.main()
