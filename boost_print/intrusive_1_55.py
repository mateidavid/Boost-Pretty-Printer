########################################
# Intrusive containers 1.55
########################################

import sys
import re
import gdb
import gdb.types

from .common import *
from . import utils

def short_ns(tag):
    if tag.startswith('boost::intrusive::'):
        return 'bi::' + tag[18:]
    else:
        return tag

@add_type_recognizer
class Generic_Hook_Type_Recognizer:
    "Type Recognizer for boost::intrusive::generic_hook"
    name = 'boost::intrusive::generic_hook-1.55'
    enabled = True
    target_re = re.compile('^boost::intrusive::generic_hook<.*>$')

    def recognize(self, t):
        if not t.tag or self.target_re.search(t.tag) == None:
            return None
        # hook_tag: default (base) or member
        hook_tag = str(t.template_argument(1).strip_typedefs())
        # link mode
        link_mode = str(t.template_argument(2)).split('::')[2]
        # node_type: first subclass, or the first subclass of the first subclass
        node_t = t.fields()[0].type
        if str(node_t.strip_typedefs()).startswith('boost::intrusive::node_holder'):
            node_t = node_t.fields()[0].type
        node_tag = str(node_t.strip_typedefs())
        return 'bi::generic_hook<' + short_ns(node_tag) + ', ' + short_ns(hook_tag) + ', ' + link_mode + '>'

@add_value_printer
class Generic_Hook_Printer:
    "Pretty Printer for boost::intrusive::generic_hook"
    printer_name = 'boost::intrusive::generic_hook'
    version = '1.55'
    type_name_re = '^boost::intrusive::generic_hook<.*>$'
    enabled = True

    def __init__(self, value):
        self.value = value

    def to_string(self):
        # the actual node is either the first subclass,
        # or the first subclass of the first subclass
        node = self.value.cast(self.value.type.fields()[0].type)
        if str(node.type.strip_typedefs()).startswith('boost::intrusive::node_holder'):
            node = node.cast(node.type.fields()[0].type)
        return str(node)

@add_type_recognizer
class Hook_Type_Recognizer:
    "Type Recognizer for boost::intrusive::*_(base|member)_hook"
    name = 'boost::intrusive::hook-1.55'
    enabled = True
    target_re = re.compile('^boost::intrusive::(avl_set|bs_set|list|set|slist|splay_set|unordered_set)_(base|member)_hook<.*>$')

    def recognize(self, t):
        if not t.tag or not self.target_re.search(t.tag):
            return None
        # just print the underlying generic hook
        generic_hook_t = t.fields()[0].type
        return Generic_Hook_Type_Recognizer().recognize(generic_hook_t)

@add_value_printer
class Hook_Printer:
    "Pretty Printer for boost::intrusive::*_(base|member)_hook"
    printer_name = 'boost::intrusive::hook'
    version = '1.55'
    type_name_re = '^boost::intrusive::(avl_set|bs_set|list|set|slist|splay_set|unordered_set)_(base|member)_hook<.*>$'
    enabled = True

    def __init__(self, value):
        self.val = value

    def to_string(self):
        # cast to and print underlying generic hook
        generic_hook_t = self.val.type.fields()[0].type
        generic_hook = self.val.cast(generic_hook_t)
        return str(generic_hook)

def get_node_traits(vtt):
    """Get node_traits type from value_traits type."""
    assert isinstance(vtt, gdb.Type), 'vtt not a gdb.Type'

    # builtin bhtraits:
    #   node_traits is 2nd template parameter
    #
    if str(vtt.strip_typedefs()).startswith('boost::intrusive::bhtraits<'):
        #print('get_node_traits: internal vtt: bhtraits', file=sys.stderr)
        return vtt.template_argument(1)

    # builtin mhtraits:
    #   hook is 2nd template parameter (e.g. "list_member_hook")
    #   generic_hook is 1st subclass of hook
    #   get_node_algo is 1st template parameter of generic_hook
    #
    #   We hard-code node_traits as a function of get_node_algo.
    #
    if str(vtt.strip_typedefs()).startswith('boost::intrusive::mhtraits<'):
        #print('get_node_traits: internal vtt: mhtraits', file=sys.stderr)
        gen_hook_t = vtt.template_argument(1).fields()[0].type
        get_node_algo_t = gen_hook_t.template_argument(0)
        voidptr_t = get_node_algo_t.template_argument(0)
        for case in utils.switch(utils.template_name(get_node_algo_t)):
            if case('boost::intrusive::get_list_node_algo'):
                return gdb.lookup_type('boost::intrusive::list_node_traits<'
                                       + str(voidptr_t) + '>')
            if case('boost::intrusive::get_slist_node_algo'):
                return gdb.lookup_type('boost::intrusive::slist_node_traits<'
                                       + str(voidptr_t) + '>')
            if case('boost::intrusive::get_set_node_algo'):
                opt_size = get_node_algo_t.template_argument(1)
                return gdb.lookup_type('boost::intrusive::rbtree_node_traits<'
                                       + str(voidptr_t) + ',' + str(opt_size) + '>')
            if case('boost::intrusive::get_avl_set_node_algo'):
                opt_size = get_node_algo_t.template_argument(1)
                return gdb.lookup_type('boost::intrusive::avltree_node_traits<'
                                       + str(voidptr_t) + ',' + str(opt_size) + '>')
            if case('boost::intrusive::get_bs_set_node_algo'):
                return gdb.lookup_type('boost::intrusive::tree_node_traits<'
                                       + str(voidptr_t) + '>')
        assert False, 'could not determine node_traits'

    # builtin trivial_value_traits:
    #   node_traits is first template parameter
    #
    if str(vtt.strip_typedefs()).startswith('boost::intrusive::trivial_value_traits<'):
        #print('get_node_traits: internal vtt: trivial_value_traits', file=sys.stderr)
        return vtt.template_argument(0)

    # if vtt is not a built-in type, try to resolve typedef
    return utils.get_inner_type(vtt, 'node_traits')


def apply_to_value_ptr(vtt, node_ptr):
    """Get value_ptr from node_ptr. `vtt` is a gdb.Type, `node_ptr` is a gdb.Value."""
    assert isinstance(vtt, gdb.Type), 'vtt not a gdb.Type'
    assert isinstance(node_ptr, gdb.Value), 'node_ptr not a gdb.Value'

    # builtin trivial_value_traits:
    #   node == value
    #
    if str(vtt.strip_typedefs()).startswith('boost::intrusive::trivial_value_traits<'):
        return node_ptr

    # builtin bhtraits
    #   we perform a 2-step upcast to accomodate for multiple base hooks
    #
    if str(vtt.strip_typedefs()).startswith('boost::intrusive::bhtraits<'):
        # first, find the tag type
        tag_t = vtt.template_argument(3)
        # find value base class with the appropriate tag
        subclass_t = None
        for f in vtt.template_argument(0).fields():
            if f.type.code != gdb.TYPE_CODE_STRUCT:
                # the remaining types aren't subclasses
                break
            t = f.type.fields()[0].type
            if (str(t.strip_typedefs()).startswith('boost::intrusive::generic_hook<')
                and t.template_argument(1).strip_typedefs() == tag_t.strip_typedefs()):
                subclass_t = t
                break
        assert subclass_t, 'no subclass hook with tag: ' + str(tag_t.strip_typedefs())
        # first upcast into generic_hook ptr with correct tag
        subclass_ptr = node_ptr.cast(subclass_t.pointer())
        val_ptr_t = utils.get_inner_type(vtt, 'pointer')
        # second upcast into value
        return subclass_ptr.cast(val_ptr_t)

    # internal mhtraits
    #   offset is 3rd template argument
    #
    if str(vtt.strip_typedefs()).startswith('boost::intrusive::mhtraits<'):
        offset = vtt.template_argument(2)
        offset_int = gdb.parse_and_eval('(size_t)(' + str(offset) + ')')
        node_ptr_int = int(node_ptr)
        val_ptr_t = utils.get_inner_type(vtt, 'pointer')
        return gdb.parse_and_eval('(' + str(val_ptr_t.strip_typedefs()) + ')(' + str(node_ptr_int - offset_int) + ')')

    return utils.call_static_method(str(vtt.strip_typedefs()) + '::to_value_ptr', node_ptr)


def apply_get_next(ntt, node_ptr):
    """Apply node_traits::get_next(). `ntt` is a gdb.Type, `node_ptr` is a gdb.Value."""
    assert isinstance(ntt, gdb.Type), 'ntt not a gdb.Type'
    assert isinstance(node_ptr, gdb.Value), 'node_ptr not a gdb.Value'

    # builtin (s)list_node_traits
    #   follow 'next_'
    #
    if (str(ntt.strip_typedefs()).startswith('boost::intrusive::list_node_traits<')
        or str(ntt.strip_typedefs()).startswith('boost::intrusive::slist_node_traits<')):
        return node_ptr['next_']

    return utils.call_static_method(str(ntt.strip_typedefs()) + '::get_next', node_ptr)

def apply_get_parent(ntt, node_ptr):
    """Apply node_traits::get_parent(). `ntt` is a gdb.Type, `node_ptr` is a gdb.Value."""
    assert isinstance(ntt, gdb.Type), 'ntt not a gdb.Type'
    assert isinstance(node_ptr, gdb.Value), 'node_ptr not a gdb.Value'

    # builtin tree_node_traits
    #   follow 'parent_'
    #
    if (utils.template_name(ntt) in
        ['boost::intrusive::rbtree_node_traits',
         'boost::intrusive::avltree_node_traits',
         'boost::intrusive::tree_node_traits']):
        return node_ptr['parent_']

    return utils.call_static_method(str(ntt.strip_typedefs()) + '::get_parent', node_ptr)

def apply_get_left(ntt, node_ptr):
    """Apply node_traits::get_left(). `ntt` is a gdb.Type, `node_ptr` is a gdb.Value."""
    assert isinstance(ntt, gdb.Type), 'ntt not a gdb.Type'
    assert isinstance(node_ptr, gdb.Value), 'node_ptr not a gdb.Value'

    # builtin tree_node_traits
    #   follow 'left_'
    #
    if (utils.template_name(ntt) in
        ['boost::intrusive::rbtree_node_traits',
         'boost::intrusive::avltree_node_traits',
         'boost::intrusive::tree_node_traits']):
        return node_ptr['left_']

    return utils.call_static_method(str(ntt.strip_typedefs()) + '::get_left', node_ptr)

def apply_get_right(ntt, node_ptr):
    """Apply node_traits::get_right(). `ntt` is a gdb.Type, `node_ptr` is a gdb.Value."""
    assert isinstance(ntt, gdb.Type), 'ntt not a gdb.Type'
    assert isinstance(node_ptr, gdb.Value), 'node_ptr not a gdb.Value'

    # builtin tree_node_traits
    #   follow 'right_'
    #
    if (utils.template_name(ntt) in
        ['boost::intrusive::rbtree_node_traits',
         'boost::intrusive::avltree_node_traits',
         'boost::intrusive::tree_node_traits']):
        return node_ptr['right_']

    return utils.call_static_method(str(ntt.strip_typedefs()) + '::get_right', node_ptr)

def apply_pointed_node(it):
    """Apply iterator::pointed_node."""
    assert isinstance(it, gdb.Value), 'it not a gdb.Value'

    # builtin iterators
    #
    if (utils.template_name(it.type) == 'boost::intrusive::list_iterator'
        or utils.template_name(it.type) == 'boost::intrusive::slist_iterator'
        or utils.template_name(it.type) == 'boost::intrusive::tree_iterator'):
        return it['members_']['nodeptr_']

    return utils.call_object_method(it, 'pointed_node')


def value_ptr_from_iiterator(it):
    # value traits is first template argument
    value_traits_t = it.type.template_argument(0)
    # apply pointed_node() to get node_ptr
    node_ptr = apply_pointed_node(it)
    return apply_to_value_ptr(value_traits_t, node_ptr)

@add_value_printer
class Iterator_Printer:
    "Pretty Printer for boost::intrusive::(list|slist|tree)_iterator"
    printer_name = 'boost::intrusive::iterator'
    version = '1.55'
    type_name_re = '^boost::intrusive::(list|slist|tree)_iterator<.*>$'
    enabled = True

    def __init__(self, value):
        self.val = value

    def to_string(self):
        value_ptr = value_ptr_from_iiterator(self.val)
        try:
            value_str = str(value_ptr.dereference())
        except:
            value_str = 'N/A'
        return str(self.val['members_']['nodeptr_']) + ' -> ' + value_str

@add_value_printer
class List_Printer:
    "Pretty Printer for boost::intrusive list and slist"
    printer_name = 'boost::intrusive::list'
    version = '1.55'
    type_name_re = '^boost::intrusive::s?list<.*>$'
    enabled = True

    class Iterator:
        def __init__(self, l):
            self.value_traits_t = l.type.fields()[0].type.template_argument(0)
            self.node_traits_t = get_node_traits(self.value_traits_t)
            self.root_node_ptr = utils.call_object_method(l, 'get_root_node')

        def __iter__(self):
            self.count = 0
            self.crt_node_ptr = apply_get_next(self.node_traits_t, self.root_node_ptr)
            return self

        def __next__(self):
            if self.crt_node_ptr == self.root_node_ptr:
                raise StopIteration
            val_ptr = apply_to_value_ptr(self.value_traits_t, self.crt_node_ptr)
            try:
                val_str = str(val_ptr.referenced_value())
            except:
                val_str = 'N/A'
            result = ('[%d; %s]' % (self.count, hex(int(val_ptr))), val_str)
            self.count = self.count + 1
            self.crt_node_ptr = apply_get_next(self.node_traits_t, self.crt_node_ptr)
            return result

    def __init__(self, l):
        self.l = l
        self.value_type = self.l.type.template_argument(0)

    def to_string (self):
        return (short_ns(utils.template_name(self.l.type))
                + '<' + str(self.value_type.strip_typedefs()) + '>')

    def children (self):
        return self.Iterator(self.l)

@add_value_printer
class Tree_Printer:
    "Pretty Printer for boost::intrusive ordered sets"
    printer_name = 'boost::intrusive::set'
    version = '1.55'
    enabled = True

    @staticmethod
    def supports(v):
        t = v.type
        d = 5
        while d > 0 and isinstance(t, gdb.Type) and utils.template_name(t) != 'boost::intrusive::bstree_impl':
            try:
                t = t.fields()[0].type
            except:
                return None
            d -= 1
        return d > 0 and isinstance(t, gdb.Type)

    class Iterator:
        def __init__(self, l):
            self.value_traits_t = l.type.fields()[0].type.template_argument(0)
            self.node_traits_t = get_node_traits(self.value_traits_t)
            self.header_node_ptr = utils.call_object_method(l, 'header_ptr')

        def __iter__(self):
            self.count = 0
            self.crt_node_ptr = apply_get_left(self.node_traits_t, self.header_node_ptr)
            return self

        def __next__(self):
            if self.crt_node_ptr == self.header_node_ptr:
                raise StopIteration
            val_ptr = apply_to_value_ptr(self.value_traits_t, self.crt_node_ptr)
            try:
                val_str = str(val_ptr.referenced_value())
            except:
                val_str = 'N/A'
            result = ('[%d; %s]' % (self.count, hex(int(val_ptr))), val_str)
            self.count = self.count + 1
            self.advance()
            return result

        def advance(self):
            n = apply_get_right(self.node_traits_t, self.crt_node_ptr)
            if n != 0:
                # if right subtree is not empty, find leftmost node in it
                self.crt_node_ptr = n
                while True:
                    n = apply_get_left(self.node_traits_t, self.crt_node_ptr)
                    if n == 0:
                        break
                    self.crt_node_ptr = n
            else:
                # if right subtree is empty, find first ancestor in whose left subtree we are
                while True:
                    old_n = self.crt_node_ptr
                    self.crt_node_ptr = apply_get_parent(self.node_traits_t, self.crt_node_ptr)
                    if self.crt_node_ptr == self.header_node_ptr:
                        break
                    n = apply_get_left(self.node_traits_t, self.crt_node_ptr)
                    if n == old_n:
                        break

    def __init__(self, l):
        self.l = l
        self.value_type = self.l.type.template_argument(0)

    def to_string (self):
        return (short_ns(utils.template_name(self.l.type))
                + '<' + str(self.value_type.strip_typedefs()) + '>')

    def children (self):
        return self.Iterator(self.l)
