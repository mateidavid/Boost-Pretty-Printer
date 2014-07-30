import sys
import re
import gdb
import gdb.types

from .common import *

@add_value_printer
class BoostIteratorRange:
    "Pretty Printer for boost::iterator_range (Boost.Range)"
    printer_name = 'boost::iterator_range'
    version = '1.40'
    type_name_re = '^boost::iterator_range<.*>$'

    class _iterator:
        def __init__(self, begin, end):
            self.item = begin
            self.end = end
            self.count = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self.item == self.end:
                raise StopIteration
            count = self.count
            self.count = self.count + 1
            elem = self.item.dereference()
            self.item = self.item + 1
            return ('[%d]' % count, elem)

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def children(self):
        return self._iterator(self.value['m_Begin'], self.value['m_End'])

    def to_string(self):
        begin = self.value['m_Begin']
        end = self.value['m_End']
        return '%s of length %d' % (self.typename, int(end - begin))

    def display_hint(self):
        return 'array'

@add_value_printer
class BoostOptional:
    "Pretty Printer for boost::optional (Boost.Optional)"
    printer_name = 'boost::optional'
    version = '1.40'
    type_name_re = '^boost::optional<(.*)>$'
    regex = re.compile(type_name_re)

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    class _iterator:
        def __init__(self, member, empty):
            self.member = member
            self.done = empty

        def __iter__(self):
            return self

        def __next__(self):
            if(self.done):
                raise StopIteration
            self.done = True
            return ('value', self.member.dereference())

    def children(self):
        initialized = self.value['m_initialized']
        if(not initialized):
            return self._iterator('', True)
        else:
            match = BoostOptional.regex.search(self.typename)
            if match:
                try:
                    membertype = gdb.lookup_type(match.group(1)).pointer()
                    member = self.value['m_storage']['dummy_']['data'].address.cast(membertype)
                    return self._iterator(member, False)
                except:
                    return self._iterator('', True)

    def to_string(self):
        initialized = self.value['m_initialized']
        if(not initialized):
            return "%s is not initialized" % self.typename
        else:
            return "%s is initialized" % self.typename

@add_value_printer
class BoostReferenceWrapper:
    "Pretty Printer for boost::reference_wrapper (Boost.Ref)"
    printer_name = 'boost::reference_wrapper'
    version = '1.40'
    type_name_re = '^boost::reference_wrapper<(.*)>$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        return '(%s) %s' % (self.typename, self.value['t_'].dereference())

@add_value_printer
class BoostTribool:
    "Pretty Printer for boost::logic::tribool (Boost.Tribool)"
    printer_name = 'boost::logic::tribool'
    version = '1.40'
    type_name_re = '^boost::logic::tribool$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        state = self.value['value']
        s = 'indeterminate'
        if(state == 0):
            s = 'false'
        elif(state == 1):
            s = 'true'
        return '(%s) %s' % (self.typename, s)

@add_value_printer
class BoostScopedPtr:
    "Pretty Printer for boost::scoped/intrusive_ptr/array (Boost.SmartPtr)"
    printer_name = 'boost::scoped/intrusive_ptr/array'
    version = '1.40'
    type_name_re = '^boost::(intrusive|scoped)_(ptr|array)<(.*)>$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        return '(%s) %s' % (self.typename, self.value['px'])

@add_value_printer
class BoostSharedPtr:
    "Pretty Printer for boost::shared/weak_ptr/array (Boost.SmartPtr)"
    printer_name = 'boost::shared/weak_ptr/array'
    version = '1.40'
    type_name_re = '^boost::(weak|shared)_(ptr|array)<(.*)>$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        if self.value['px'] == 0x0:
            return '(%s) %s' % (self.typename, self.value['px'])
        countobj = self.value['pn']['pi_'].dereference()
        refcount = countobj['use_count_']
        weakcount = countobj['weak_count_']
        return '(%s) (count %d, weak count %d) %s' % (self.typename,
                                                      refcount, weakcount,
                                                      self.value['px'])

@add_value_printer
class BoostCircular:
    "Pretty Printer for boost::circular_buffer (Boost.Circular)"
    printer_name = 'boost::circular_buffer'
    version = '1.40'
    type_name_re = '^boost::circular_buffer<(.*)>$'

    class _iterator:
        def __init__(self, first, last, buff, end, size):
            self.item = first # virtual beginning of the circular buffer
            self.last = last  # virtual end of the circular buffer (one behind the last element).
            self.buff = buff  # internal buffer used for storing elements in the circular buffer
            self.end = end    # internal buffer's end (end of the storage space).
            self.size = size
            self.capa = int(end-buff)
            self.count = 0

        def __iter__(self):
            return self

        def __next__(self):
            if self.count == self.size:
                raise StopIteration
            count = self.count
            crt=self.buff + (count + self.item - self.buff) % self.capa
            elem = crt.dereference()
            self.count = self.count + 1
            return ('[%d]' % count, elem)




            if self.item == self.last:
                raise StopIteration
            count = self.count
            self.count = self.count + 1
            elem = self.item.dereference()
            self.item = self.item + 1
            if self.item == self.end:
                self.item == self.buff
            return ('[%d]' % count, elem)

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def children(self):
        return self._iterator(self.value['m_first'], self.value['m_last'], self.value['m_buff'], self.value['m_end'], self.value['m_size'])

    def to_string(self):
        first = self.value['m_first']
        last = self.value['m_last']
        buff = self.value['m_buff']
        end = self.value['m_end']
        size = self.value['m_size']
        return '%s of length %d/%d' % (self.typename, int(size), int(end-buff))

    def display_hint(self):
        return 'array'

@add_value_printer
class BoostArray:
    "Pretty Printer for boost::array (Boost.Array)"
    printer_name = 'boost::array'
    version = '1.40'
    type_name_re = '^boost::array<(.*)>$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        return str(self.value['elems'])

    def display_hint(self):
        return 'array'

@add_value_printer
class BoostVariant:
    "Pretty Printer for boost::variant (Boost.Variant)"
    printer_name = 'boost::variant'
    version = '1.40'
    type_name_re = '^boost::variant<(.*)>$'
    regex = re.compile(type_name_re)

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        m = BoostVariant.regex.search(self.typename)
        # TODO this breaks with boost::variant< foo<a,b>, bar >!
        types = [s.strip() for s in m.group(1).split(',')]
        which = int(self.value['which_'])
        type = types[which]
        data = ''
        try:
            ptrtype = gdb.lookup_type(type).pointer()
            data = self.value['storage_']['data_']['buf'].address.cast(ptrtype)
        except:
            data = self.value['storage_']['data_']['buf']
        return '(boost::variant<...>) which (%d) = %s value = %s' % (which,
                                                                     type,
                                                                     data.dereference())

@add_value_printer
class BoostUuid:
    "Pretty Printer for boost::uuids::uuid (Boost.Uuid)"
    printer_name = 'boost::uuids::uuid'
    version = '1.40'
    type_name_re = '^boost::uuids::uuid$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        u = (self.value['data'][i] for i in range(16))
        s = 'xxxx-xx-xx-xx-xxxxxx'.replace('x', '%02x') % tuple(u)
        return '(%s) %s' % (self.typename, s)

##################################################
# boost::intrusive::set                          #
##################################################

def get_named_template_argument(gdb_type, arg_name):
    n = 0;
    while True:
        try:
            arg = gdb_type.strip_typedefs().template_argument(n)
            if (str(arg).startswith(arg_name)):
                return arg
            n += 1
        except RuntimeError:
            return None

def intrusive_container_has_size_member(intrusive_container_type):
    constant_size_arg = get_named_template_argument(intrusive_container_type, "boost::intrusive::constant_time_size")
    if not constant_size_arg:
        return True
    if str(constant_size_arg.template_argument(0)) == 'false':
        return False
    return True

def intrusive_iterator_to_string(iterator_value):
    opttype = iterator_value.type.template_argument(0).template_argument(0)

    base_hook_traits = get_named_template_argument(opttype, "boost::intrusive::detail::base_hook_traits")
    if base_hook_traits:
        value_type = base_hook_traits.template_argument(0)
        return iterator_value["members_"]["nodeptr_"].cast(value_type.pointer()).dereference()

    member_hook_traits = get_named_template_argument(opttype, "boost::intrusive::detail::member_hook_traits")
    if member_hook_traits:
        value_type = member_hook_traits.template_argument(0)
        member_offset = member_hook_traits.template_argument(2).cast(gdb.lookup_type("size_t"))
        currentElementAddress = iterator_value["members_"]["nodeptr_"].cast(gdb.lookup_type("size_t")) - member_offset
        return currentElementAddress.cast(value_type.pointer()).dereference()

    return iterator_value["members_"]["nodeptr_"]


class BoostIntrusiveRbtreeIterator:
    def __init__(self, rbTreeHeader, elementPointerType, memberOffset=0):
        self.header = rbTreeHeader
        self.memberOffset = memberOffset
        if memberOffset == 0:
            self.nodeType = elementPointerType
        else:
            self.nodeType = gdb.lookup_type("boost::intrusive::rbtree_node<void*>").pointer();
            self.elementPointerType = elementPointerType
        self.node = rbTreeHeader['left_'].cast(self.nodeType)

    def __iter__(self):
        return self

    def getElementPointerFromNodePointer(self):
        if self.memberOffset == 0:
            return self.node
        else:
            currentElementAddress = self.node.cast(gdb.lookup_type("size_t")) - self.memberOffset
            return currentElementAddress.cast(self.elementPointerType)

    def __next__(self):
        # empty set or reached rightmost leaf
        if not self.node:
            raise StopIteration
        result = self.getElementPointerFromNodePointer()
        if self.node != self.header["right_"].cast(self.nodeType):
            # Compute the next node.
            node = self.node
            if node.dereference()['right_']:
                node = node.dereference()['right_']
                while node.dereference()['left_']:
                    node = node.dereference()['left_']
            else:
                parent = node.dereference()['parent_']
                while node == parent.dereference()['right_']:
                    node = parent
                    parent = parent.dereference()['parent_']
                if node.dereference()['right_'] != parent:
                    node = parent
            self.node = node.cast(self.nodeType)
        else:
            self.node = 0
        return result

@add_value_printer
class BoostIntrusiveSet:
    "Pretty Printer for boost::intrusive::set (Boost.Intrusive)"
    printer_name = 'boost::intrusive::set'
    version = '1.40'
    type_name_re = '^boost::intrusive::set<.*>$'
    enabled = False

    class _iter:
        def __init__(self, rbiter):
            self.rbiter = rbiter
            self.count = 0

        def __iter__(self):
            return self

        def __next__(self):
            item = self.rbiter.next().dereference()
            result = ('[%d]' % self.count, item)
            self.count = self.count + 1
            return result

    def __init__(self, value):
        self.typename = value.type_name
        self.val = value
        self.elementType = self.val.type.strip_typedefs().template_argument(0)

    def getHeader(self):
        return self.val["tree_"]["data_"]["node_plus_pred_"]["header_plus_size_"]["header_"]

    def getSize(self):
        return self.val["tree_"]["data_"]["node_plus_pred_"]["header_plus_size_"]["size_"]

    def hasElements(self):
        header = self.getHeader()
        firstElement = header["parent_"]
        if firstElement:
            return True
        else:
            return False

    def to_string (self):
        if (intrusive_container_has_size_member(self.val.type)):
            return "boost::intrusive::set<%s> with %d elements" % (self.elementType, self.getSize())
        elif (self.hasElements()):
            return "non-empty boost::intrusive::set<%s>" % self.elementType
        else:
            return "empty boost::intrusive::set<%s>" % self.elementType

    def children (self):
        elementPointerType = self.elementType.pointer()
        member_hook = get_named_template_argument(self.val.type, "boost::intrusive::member_hook")
        if member_hook:
            memberOffset = member_hook.template_argument(2).cast(gdb.lookup_type("size_t"))
            return self._iter (BoostIntrusiveRbtreeIterator(self.getHeader(), elementPointerType, memberOffset))
        else:
            return self._iter (BoostIntrusiveRbtreeIterator(self.getHeader(), elementPointerType))


@add_value_printer
class BoostIntrusiveTreeIterator:
    "Pretty Printer for boost::intrusive::set<*>::iterator (Boost.Intrusive)"
    printer_name = 'boost::intrusive::tree_iterator'
    version = '1.40'
    type_name_re = '^boost::intrusive::tree_iterator<.*>$'
    enabled = False

    def __init__(self, value):
        self.val = value
        self.typename = value.type_name

    def to_string(self):
        return intrusive_iterator_to_string(self.val)


##################################################
# boost::intrusive::list                         #
##################################################

class BoostIntrusiveListIterator:
    def __init__(self, listHeader, elementPointerType, memberOffset=0):
        self.header = listHeader
        self.memberOffset = memberOffset
        if memberOffset == 0:
            self.nodeType = elementPointerType
        else:
            self.nodeType = gdb.lookup_type("boost::intrusive::list_node<void*>").pointer();
            self.elementPointerType = elementPointerType
        nextNode = listHeader['next_']
        if nextNode != listHeader.address:
            self.node = nextNode.cast(self.nodeType)
        else:
            self.node = 0

    def __iter__(self):
        return self

    def getElementPointerFromNodePointer(self):
        if self.memberOffset == 0:
            return self.node
        else:
            currentElementAddress = self.node.cast(gdb.lookup_type("size_t")) - self.memberOffset
            return currentElementAddress.cast(self.elementPointerType)

    def __next__(self):
        # empty list or reached end
        if not self.node:
            raise StopIteration
        result = self.getElementPointerFromNodePointer()
        nextNode = self.node['next_']
        if nextNode != self.header.address:
            self.node = nextNode.cast(self.nodeType)
        else:
            self.node = 0
        return result

@add_value_printer
class BoostIntrusiveList:
    "Pretty Printer for boost::intrusive::list (Boost.Intrusive)"
    printer_name = 'boost::intrusive::list'
    version = '1.40'
    type_name_re = '^boost::intrusive::list<.*>$'
    enabled = False

    class _iter:
        def __init__(self, listiter):
            self.listiter = listiter
            self.count = 0

        def __iter__(self):
            return self

        def __next__(self):
            item = self.listiter.next().dereference()
            result = ('[%d]' % self.count, item)
            self.count = self.count + 1
            return result

    def __init__(self, value):
        self.typename = value.type_name
        self.val = value
        self.elementType = self.val.type.strip_typedefs().template_argument(0)

    def getHeader(self):
        return self.val["data_"]["root_plus_size_"]["root_"]

    def getSize(self):
        return self.val["data_"]["root_plus_size_"]["size_"]

    def hasElements(self):
        header = self.getHeader()
        firstElement = header["next_"]
        rootElement = header.address
        if firstElement != rootElement:
            return True
        else:
            return False

    def to_string (self):
        if (intrusive_container_has_size_member(self.val.type)):
            return "boost::intrusive::list<%s> with %d elements" % (self.elementType, self.getSize())
        elif (self.hasElements()):
            return "non-empty boost::intrusive::list<%s>" % self.elementType
        else:
            return "empty boost::intrusive::list<%s>" % self.elementType

    def children (self):
        elementPointerType = self.elementType.pointer()
        member_hook = get_named_template_argument(self.val.type, "boost::intrusive::member_hook")
        if member_hook:
            memberOffset = member_hook.template_argument(2).cast(gdb.lookup_type("size_t"))
            return self._iter (BoostIntrusiveListIterator(self.getHeader(), elementPointerType, memberOffset))
        else:
            return self._iter (BoostIntrusiveListIterator(self.getHeader(), elementPointerType))

@add_value_printer
class BoostIntrusiveListIterator:
    "Pretty Printer for boost::intrusive::list<*>::iterator (Boost.Intrusive)"
    printer_name = 'boost::intrusive::list_iterator'
    version = '1.40'
    type_name_re = '^boost::intrusive::list_iterator<.*>$'
    enabled = False

    def __init__(self, value):
        self.val = value

    def to_string(self):
        return intrusive_iterator_to_string(self.val)


@add_value_printer
class BoostGregorianDate:
    "Pretty Printer for boost::gregorian::date"
    printer_name = 'boost::gregorian::date'
    version = '1.40'
    type_name_re = '^boost::gregorian::date$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        n = int(self.value['days_'])
        # Check for uninitialized case
        if n==2**32-2:
            return '(%s) uninitialized' % self.typename
        # Convert date number to year-month-day
        a = n + 32044
        b = (4*a + 3) / 146097
        c = a - (146097*b)/4
        d = (4*c + 3)/1461
        e = c - (1461*d)/4
        m = (5*e + 2)/153
        day = e + 1 - (153*m + 2)/5
        month = m + 3 - 12*(m/10)
        year = 100*b + d - 4800 + (m/10)
        return '(%s) %4d-%02d-%02d' % (self.typename, year,month,day)

@add_value_printer
class BoostPosixTimePTime:
    "Pretty Printer for boost::posix_time::ptime"
    printer_name = 'boost::posix_time::ptime'
    version = '1.40'
    type_name_re = '^boost::posix_time::ptime$'

    def __init__(self, value):
        self.typename = value.type_name
        self.value = value

    def to_string(self):
        n = int(self.value['time_']['time_count_']['value_'])
        # Check for uninitialized case
        if n==2**63-2:
            return '(%s) uninitialized' % self.typename
        # Represent time in a raw fashion
        return '(%s) %d' % (self.typename, n)
