import sys
import gdb

from .common import *

def execute(cmd):
    #print('execute: ' + cmd, file=sys.stderr)
    return gdb.execute(cmd)
def parse_and_eval(cmd):
    #print('parse_and_eval: ' + cmd, file=sys.stderr)
    return gdb.parse_and_eval(cmd)

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

def get_type_qualifiers(t):
    """Return the qualifiers of a gdb.Type: const, volatile, and reference."""
    assert isinstance(t, gdb.Type), '"t" not a gdb.Type'
    t = t.strip_typedefs()
    qualifiers = ''
    if t.code == gdb.TYPE_CODE_REF:
        qualifiers = '&' + qualifiers
        t = t.target()
    if t == t.unqualified():
        pass
    elif t == t.unqualified().const():
        qualifiers = 'c' + qualifiers
    elif t == t.unqualified().volatile():
        qualifiers = 'v' + qualifiers
    elif t == t.unqualified().const().volatile():
        qualifiers = 'cv' + qualifiers
    else:
        assert False, 'could not determine type qualifiers'
    return qualifiers

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
    """Save gdb.Value `v` as gdb variable `s`."""
    assert isinstance(v, gdb.Value), 'arg 1 not a gdb.Value'
    assert isinstance(s, str), 'arg 2 not a string'
    _aux_save_value_as_variable(v)
    execute('set var ' + s + ' = $_aux_save_value_as_variable()')

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
        args_to_eval.append(to_eval(arg, '$_call_object_method_arg_%s' % i + 1))
    return parse_and_eval(to_eval(v, '$_call_object_method_arg_0') + '.' + f
                          + '(' + ', '.join(args_to_eval) + ')')

# convenience function: $new(p, *args)
#
# Args:
#   p: a gdb.Value that is a pointer to desired type
#   *args: list of gdb.Value objects to pass to constructor
#
class new_func(gdb.Function):
    def __init__(self):
        super(new_func, self).__init__('new')
    def invoke(self, p, *args):
        assert p.type.strip_typedefs().code == gdb.TYPE_CODE_PTR, '"p" is not a pointer'
        t = p.type.strip_typedefs().target()
        type_name = str(t.strip_typedefs())
        # allocate object
        execute('set $_new_func_p = (%s *)malloc(sizeof(%s))' % (type_name, type_name))
        # run constructor
        i = 0
        args_to_eval = list()
        for arg in args:
            assert isinstance(arg, gdb.Value), 'extra argument %s not a gdb.Value' % str(i + 1)
            args_to_eval.append(to_eval(arg, '$_new_func_arg_%s' % str(i + 1)))
        constructor_name = template_name(t).split(':')[-1]
        execute('call $_new_func_p->' + constructor_name
                + '(' + ', '.join(args_to_eval) + ')')
        return parse_and_eval('$_new_func_p')
_new = new_func()

# convenience function: $delete(p)
#
# Args:
#   p: a gdb.Value object that is a pointer
class del_func(gdb.Function):
    def __init__(self):
        super(del_func, self).__init__('del')
    def invoke(self, p):
        assert p.type.strip_typedefs().code == gdb.TYPE_CODE_PTR, '"p" is not a pointer'
        t = p.type.strip_typedefs().target()
        save_value_as_variable(p, '$_del_func_p')
        # run destructor first
        destructor_name = '~' + template_name(t).split(':')[-1]
        try:
            execute('call $_del_func_p->' + destructor_name + '()')
        except:
            #print('could not run destructor of type: ' + str(t), file=sys.stderr)
            pass
        # then deallocate
        execute('call free($_del_func_p)')
        return parse_and_eval('(void)0')
_del = del_func()

# Bypass static method calls
#
# key: (str, str)
#   1st argument is the enclosing type/template name, stripped of typedefs.
#   2nd argument is the method name.
# value: python function
#   Call this function instead of calling original static method.
#   If the 1st key is a template name, the function is given one extra
#   parameter, the type name that matched.
#
static_method = dict()

def call_static_method(t, f, *args):
    """Apply static method `t`::`f` to gdb.Value objects in `args`.

    If (str(`t`), `f`) matches a key in `static_method`, interpret
    dictionary value as a python function to call instead,
    passing it arguments `*args`.

    Next, if (template_name(`t`), `f`) matches a key, interpret
    dictionary value as a python function to call instead,
    passing it `t` as first argument, then `*args`.

    Args:
      `t`: a gdb.Type
      `f`: a str
      `args`: gdb.Value objects

    Raises:
      gdb.error, if call fails.
    """
    assert isinstance(t, gdb.Type), '"t" not a gdb.Type'
    assert isinstance(f, str), '"f" not a string'

    # first, try the type name bypass
    if (str(t.strip_typedefs()), f) in static_method:
        f_to_call = static_method[(str(t.strip_typedefs()), f)]
        assert callable(f_to_call), '"f_to_call" not callable'
        return f_to_call(*args)

    # next, try the template name bypass
    if (template_name(t), f) in static_method:
        f_to_call = static_method[(template_name(t), f)]
        assert callable(f_to_call), '"f_to_call" not callable'
        return f_to_call(t, *args)

    # construct argument list
    i = 0
    args_to_eval = list()
    for arg in args:
        assert isinstance(arg, gdb.Value), 'extra argument %s not a gdb.Value' % i
        args_to_eval.append(to_eval(arg, '$_call_static_method_arg_%s' % i))
    # eval in gdb
    cmd = str(t) + '::' + f + '(' + ', '.join(args_to_eval) + ')'
    try:
        return parse_and_eval(cmd)
    except:
        print('call_static_method:\n' +
              '\tcall failed: ' + cmd + '\n' +
              '\tto bypass call with a python function <f>, use:\n' +
              '\t  py boost_print.static_method[("' + str(t.strip_typedefs())
              + '", "' + f + '")] = <f>',
              file=sys.stderr)
        raise gdb.error


# Bypass inner type deduction
#
# key: (str, str, str)
#   1st argument is outter type/template name, stripped of typedefs.
#   2nd argument is inner typedef name to look for.
# value: gdb.Type, str, or python function
#   If value is a gdb.Type or str, return the corresponding type
#   instead of accessing the inner type.
#   If value is a function, call it giving the outter type as argument.
#
inner_type = dict()

def get_inner_type(t, s):
    """
    Fetch inner typedef `t`::`s`.

    If either (str(`t`), `s`) or (template_name(`t`), `s`) is a key in `inner_type`:
    if value is gdb.Value, return that instead;
    if value is a str, lookup the corresponding type and return it;
    if value is a function, call it with argument `t`, and return its value.

    Args:
      `t`: a gdb.Type
      `s`: a string

    Returns:
      A gdb.Type object corresponding to the inner type.

    Raises:
      gdb.error, if inner type is not found.
    """
    assert isinstance(t, gdb.Type), 'arg not a gdb.Type'
    assert isinstance(s, str), 's not a str'

    v = None
    # first, try the type name bypass
    if (str(t.strip_typedefs()), s) in inner_type:
        v = inner_type[(str(t.strip_typedefs()), s)]
    # next, try the template name bypass
    elif (template_name(t), s) in inner_type:
        v = inner_type[(template_name(t), s)]

    if isinstance(v, gdb.Type):
        return v
    elif isinstance(v, str):
        return gdb.lookup_type(v)
    elif callable(v):
        return v(t)

    # finally, try plain inner type access
    inner_type_name = str(t.strip_typedefs()) + '::' + s
    try:
        return gdb.lookup_type(inner_type_name)
    except gdb.error:
        print('get_inner_type:\n' +
              '\tfailed to find type: ' + inner_type_name + '\n' +
              '\tto bypass this failure, add the result manually with:\n' +
              '\t  py boost_print.inner_type[("' +
              str(t.strip_typedefs()) + '", "' + s + '")] = <type>',
              file=sys.stderr)
        raise gdb.error


# Raw pointer transformation
#
# key: str
#   The type/template name of pointer-like type.
# value: function
#   Python function to call to obtain a raw pointer.
#
raw_ptr = dict()

def get_raw_ptr(p):
    """
    Cast pointer-like object `p` into a raw pointer.

    If `p` is a pointer, it is returned unchanged.

    If the type or template name of `p` is a key in `raw_ptr`, the associated value
    is interpreted as a function to call to produce the raw pointer.

    If no corresponding entry is found in `raw_ptr`,
    an attempt is made to call `p.operator->()`.
    """
    assert isinstance(p, gdb.Value), '"p" not a gdb.Value'

    if p.type.strip_typedefs().code == gdb.TYPE_CODE_PTR:
        return p

    f = None
    if str(p.type.strip_typedefs()) in raw_ptr:
        f = raw_ptr[str(p.type.strip_typedefs())]
        assert callable(f), '"f" not callable'
    elif template_name(p.type) in raw_ptr:
        f = raw_ptr[template_name(p.type)]
        assert callable(f), '"f" not callable'

    if f:
        return f(p)

    p_str = to_eval(p, '$_get_raw_ptr_p')
    #save_value_as_variable(p, '$_p')
    try:
        return parse_and_eval(p_str +'.operator->()')
    except gdb.error:
        print('get_raw_ptr:\n'
              + '\tcall to operator->() failed on type: '
              + str(p.type.strip_typedefs()) + '\n'
              + '\tto bypass this with python function <f>, add:\n'
              + '\t  py boost_print.raw_ptr["' +
              str(p.type.strip_typedefs()) + '"] = <f>',
              file=sys.stderr)
        raise gdb.error

# Null value checker
#
# key: str
#   Type or template name, stripped of typedefs, of pointer-like type.
# value: function
#   Call function with argument a value of pointer-like type to determine if
#   value represents null.
null_dict = dict()

def is_null(p):
    """
    Check if `p` is null.

    If `p` is a pointer, check if it is 0 or not.

    If the type or template name of `p` appear in `null_dict`, call the corresponding
    value with argument `p`.
    """
    assert isinstance(p, gdb.Value), '"p" not a gdb.Value'

    if p.type.strip_typedefs().code == gdb.TYPE_CODE_PTR:
        return int(p) == 0

    f = None
    if str(p.type.strip_typedefs()) in null_dict:
        f = null_dict[str(p.type.strip_typedefs())]
        assert callable(f), '"f" not callable'
    elif template_name(p.type) in null_dict:
        f = null_dict[template_name(p.type)]
        assert callable(f), '"f" not callable'

    if f:
        return f(p)

    print('is_null:\n'
          + '\tcannot run is_null() on type: ' + str(p.type.strip_typedefs()) + '\n'
          + '\tto bypass this with python function <f>, add:\n'
          + '\t  py boost_print.null_dict["' + str(p.type.strip_typedefs()) + '"] = <f>',
          file=sys.stderr)
    raise gdb.error

def _add_to_dict(d, *keys):
    """Decorator that adds its argument object to  dict `d` under every key in `*keys`."""
    assert isinstance(d, dict), '"d" not a dict'
    def _aux_decorator(obj):
        for k in keys:
            d[k] = obj
        return None
    return _aux_decorator
