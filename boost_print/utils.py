import sys
import gdb

from .common import *

def template_name(t):
    """Get template name of type t."""
    assert isinstance(t, gdb.Type), 't is not a gdb.Type'
    return str(t.strip_typedefs()).split('<')[0]

class _aux_save_value_as_variable(gdb.Function):
    def __init__(self, v):
        super(_aux_save_value_as_variable, self).__init__('_aux_save_value_as_variable')
        self.value = v
    def invoke(self):
        return self.value

def save_value_as_variable(v, s):
    """Save gdb.Value v as gdb variable s."""
    assert isinstance(v, gdb.Value), 'arg 1 not a gdb.Value'
    assert isinstance(s, str), 'arg 2 not a string'
    _aux_save_value_as_variable(v)
    gdb.execute('set var ' + s + ' = $_aux_save_value_as_variable()')

def to_eval(val, var_name = None):
    """
    Return string that, when evaluated, returns the given gdb.Value.

    If <val> has an adddress, the string returned will be of the form:
    "(*(<val.type> *)(<val.address>))".

    If <val> has no address, it is first saved as variable <var_name>,
    then the string returned is "<var_name>".
    """
    assert isinstance(val, gdb.Value), '"val" not a gdb.Value'
    if val.address:
        return '(*(' + str(val.type) + ' *)(' + hex(int(val.address)) + '))'
    else:
        assert isinstance(var_name, str), '"var_name" not a string'
        save_value_as_variable(val, var_name)
        return var_name

def call_object_method(v, f, *args):
    """Apply method to given object."""
    assert isinstance(v, gdb.Value), '"v" not a gdb.Value'
    assert isinstance(f, str), '"f" not a string'
    i = 0
    args_to_eval = list()
    for arg in args:
        assert isinstance(arg, gdb.Value), 'extra argument %s not a gdb.Value' % i + 1
        args_to_eval.append(to_eval(arg, '$_arg_%s' % i + 1))
    return gdb.parse_and_eval(to_eval(v, '$_arg_0') + '.' + f + '(' + ', '.join(args_to_eval) + ')')

def call_static_method(f, *args):
    """Apply static method to given gdb.Value objects.

    If `f` matches a key in `_static_method`, interpret dictionary value as a
    python function to call instead.
    """
    assert isinstance(f, str), '"f" not a string'
    if f in bypass_static_method:
        return bypass_static_method[f](*args)
    # construct argument list
    i = 0
    args_to_eval = list()
    for arg in args:
        assert isinstance(arg, gdb.Value), 'extra argument %s not a gdb.Value' % i
        args_to_eval.append(to_eval(arg, '$_arg_%s' % i))
    # eval in gdb
    try:
        return gdb.parse_and_eval(f + '(' + ', '.join(args_to_eval) + ')')
    except:
        print('call_static_method:\n' +
              '\tcall failed: ' + f + '(' + ', '.join(args_to_eval) + ')\n' +
              '\tto bypass call with a python function <f>, use:\n' +
              '\t  py boost_print.bypass_static_method["' + f + '"] = <f>',
              file=sys.stderr)
        raise gdb.error

def get_inner_type(t, s):
    """Fetch inner type defined inside of an outter type.

    Before attempting to retrieve the inner type, the `_inner_type` table in consulted.
    If it contains an element with key `(<t>, <s>)`, the corresponding entry
    is interpreted as a string containing type name to return.

    Args:
      t (gdb.Type): Outter type
      s (str): Inner type

    Returns:
      A gdb.Type object corresponding to the inner type.

    Raises:
      gdb.error, if inner type is not found.
    """
    assert isinstance(t, gdb.Type), 'arg not a gdb.Type'
    assert isinstance(s, str), 's not a str'
    if (str(t.strip_typedefs()), s) in bypass_inner_type:
        return gdb.lookup_type(bypass_inner_type[(str(t.strip_typedefs()), s)])
    try:
        return gdb.lookup_type(str(t.strip_typedefs()) + '::' + s)
    except gdb.error:
        print('get_inner_type:\n' +
              '\tfailed to find type: ' + str(t.strip_typedefs()) + '::' + s + '\n' +
              '\tto resolve this failure, add the reulst manually with:\n' +
              '\t  py boost_print.bypass_inner_type[("' +
              str(t.strip_typedefs()) + '", "' + s + '")] = "<type>"',
              file=sys.stderr)
        raise gdb.error

# Ref:
# http://code.activestate.com/recipes/410692/
#
class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration
    
    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args:
            self.fall = True
            return True
        else:
            return False
