import sys
import re
import gdb
import gdb.types
import gdb.printing

from .utils import *

# check "ptype/mtr" is supported
gdb.execute('ptype/mtr void', True, True)

class GDB_Value_Wrapper(gdb.Value):
    "Wrapper class for gdb.Value that allows setting custom attributes."
    pass

###
### Individual value printers appear in various .py files.
###
### Relevant fields:
###
### - 'printer_name' : Subprinter name used by gdb. (Required.) If it contains
###     regex operators, they must be escaped when refering to it from gdb.
### - 'version' : Appended to the subprinter name. (Optional.)
### - 'supports(GDB_Value_Wrapper)' classmethod : If it exists, it is used to
###     determine if the Printer supports the given object.
### - 'type_name_re' : If 'supports(basic_type)' doesn't exist, a default
###     version is used which simply tests whether the type name matches this
###     re. (Either supports() or type_name_re is required.)
### - 'enabled' : If this exists and is set to false, disable printer.
### - '__init__' : Its only argument is a GDB_Value_Wrapper.
###

class Printer_Gen(object):
    "Value Printer Generator"
    class SubPrinter_Gen(object):
        def match_re(self, v):
            return self.re.search(str(v.basic_type)) != None

        def __init__(self, Printer):
            self.name = Printer.printer_name
            if hasattr(Printer, 'version'):
                self.name += '-' + Printer.version
            if hasattr(Printer, 'enabled'):
                self.enabled = Printer.enabled
            else:
                self.enabled = True
            if hasattr(Printer, 'supports'):
                self.re = None
                self.supports = Printer.supports
            else:
                self.re = re.compile(Printer.type_name_re)
                self.supports = self.match_re
            self.Printer = Printer

        def __call__(self, v):
            if not self.enabled:
                return None
            if self.supports(v):
                v.type_name = str(v.basic_type)
                return self.Printer(v)
            return None

    def __init__(self, name):
        self.name = name
        self.enabled = True
        self.subprinters = []

    def add(self, Printer):
        self.subprinters.append(Printer_Gen.SubPrinter_Gen(Printer))

    def __call__(self, value):
        qualifiers = get_type_qualifiers(value.type)
        v = GDB_Value_Wrapper(value.cast(gdb.types.get_basic_type(value.type)))
        v.qualifiers = qualifiers
        v.basic_type = v.type
        for subprinter_gen in self.subprinters:
            printer = subprinter_gen(v)
            if printer != None:
                return printer
        return None

class Type_Printer_Gen:
    "Type Printer Generator"

    def __init__(self, Type_Recognizer):
        self.name = Type_Recognizer.name
        self.enabled = Type_Recognizer.enabled
        self.Type_Recognizer = Type_Recognizer

    def instantiate(self):
        return self.Type_Recognizer()

printer_gen = Printer_Gen('boost')
trivial_printer_gen = Printer_Gen('trivial')
type_printer_list = list()

# This function registers the top-level Printer generator with gdb.
# This should be called from .gdbinit.
def register_printers(obj = None):
    "Register printers with objfile obj."
    gdb.printing.register_pretty_printer(obj, printer_gen)
    gdb.printing.register_pretty_printer(obj, trivial_printer_gen)
    for tp in type_printer_list:
        gdb.types.register_type_printer(obj, tp)

def add_value_printer(Printer):
    "Add a value printer"
    printer_gen.add(Printer)
    return Printer

def _cant_add_value_printer(Printer):
    print('Printer [%s] not supported by this gdb version' % Printer.printer_name,
          file=sys.stderr)
    return Printer

# Register value printer with the top-level printer generator.
def cond_add_value_printer(cond = True):
    "Conditionally add a value printer"
    if cond:
        return add_value_printer
    else:
        return _cant_add_value_printer

def add_type_recognizer(Type_Recognizer):
    "Add a type recognizer"
    type_printer_list.append(Type_Printer_Gen(Type_Recognizer))
    return Type_Recognizer

def _cant_add_type_recognizer(Type_Recognizer):
    print('Type Recognizer [%s] not supported by this gdb version' % Type_Recognizer.name,
          file=sys.stderr)
    return Type_Recognizer

# Register type recognizer with the top-level type printer list.
def cond_add_type_recognizer(cond = True):
    "Conditionally add a type recognizer"
    if cond:
        return add_type_recognizer
    else:
        return _cant_add_type_recognizer

# Add trivial printers, even from inside gdb. E.g.:
#
#   py boost_print.add_trivial_printer("List_Obj", lambda v: v['_val'])
#     - for every object v of type "List_Obj", simply print v._val
#
def add_trivial_printer(type_name, fcn):
    """
    Add a trivial printer.

    For a value v of type matching `type_name`, print it by invoking `fcn`(v).
    """
    class Printer:
        printer_name = type_name
        type_name_re = '^' + type_name + '$'
        f = fcn
        def __init__(self, v):
            self.v = v
        def to_string(self):
            return str(Printer.f(self.v))
    trivial_printer_gen.add(Printer)
