__licence__ = "MIT"
__version__ = "0.1.2"
__author__ = "Scott Griffiths, Markus Juenemann"
from ubinascii import hexlify, unhexlify
from ustruct import pack, unpack
byteorder = "little"
bytealigned = False
MAX_CHARS = 250

class Error(Exception):
    def __init__(self, *params):
        self.msg = params[0] if params else ''
        self.params = params[1:]

    def __str__(self):
        if self.params:
            return self.msg.format(*self.params)
        return self.msg

class ReadError(IndexError):
    def __init__(self, *params):
        self.msg = params[0] if params else ''
        self.params = params[1:]

    def __str__(self):
        if self.params:
            return self.msg.format(*self.params)
        return self.msg

class InterpretError(ValueError):
    def __init__(self, *params):
        self.msg = params[0] if params else ''
        self.params = params[1:]

    def __str__(self):
        if self.params:
            return self.msg.format(*self.params)
        return self.msg

class ByteAlignError(Error):
    def __init__(self, *params):
        Error.__init__(self, *params)

class CreationError(ValueError):
    def __init__(self, *params):
        self.msg = params[0] if params else ''
        self.params = params[1:]

    def __str__(self):
        if self.params:
            return self.msg.format(*self.params)
        return self.msg

class ConstByteStore(object):
    __slots__ = ('offset', '_rawarray', 'bitlength')

    def __init__(self, data, bitlength=None, offset=None):
        self._rawarray = data
        if offset is None:
            offset = 0
        if bitlength is None:
            bitlength = 8 * len(data) - offset
        self.offset = offset
        self.bitlength = bitlength

    def getbit(self, pos):
        assert 0 <= pos < self.bitlength
        byte, bit = divmod(self.offset + pos, 8)
        return bool(self._rawarray[byte] & (128 >> bit))

    def getbyte(self, pos):
        return self._rawarray[pos]

    def getbyteslice(self, start, end):
        c = self._rawarray[start:end]
        return c

    @property
    def bytelength(self):
        if not self.bitlength:
            return 0
        sb = self.offset // 8
        eb = (self.offset + self.bitlength - 1) // 8
        return eb - sb + 1

    def __copy__(self):
        return ByteStore(self._rawarray[:], self.bitlength, self.offset)

    def _appendstore(self, store):
        if not store.bitlength:
            return

        store = offsetcopy(store, (self.offset + self.bitlength) % 8)
        if store.offset:
            popval = self._rawarray[-1]
            self._rawarray = self._rawarray[:-1]
            joinval = (popval & (255 ^ (255 >> store.offset)) |
                       (store.getbyte(0) & (255 >> store.offset)))
            self._rawarray.append(joinval)
            self._rawarray.extend(store._rawarray[1:])
        else:
            self._rawarray.extend(store._rawarray)
        self.bitlength += store.bitlength

    def _prependstore(self, store):
        if not store.bitlength:
            return
        store = offsetcopy(store, (self.offset - store.bitlength) % 8)
        assert (store.offset + store.bitlength) % 8 == self.offset % 8
        bit_offset = self.offset % 8
        if bit_offset:
            store.setbyte(-1, (store.getbyte(-1) & (255 ^ (255 >> bit_offset)) |
                               (self._rawarray[self.byteoffset] & (255 >> bit_offset))))
            store._rawarray.extend(
                self._rawarray[self.byteoffset + 1: self.byteoffset + self.bytelength])
        else:
            store._rawarray.extend(
                self._rawarray[self.byteoffset: self.byteoffset + self.bytelength])
        self._rawarray = store._rawarray
        self.offset = store.offset
        self.bitlength += store.bitlength

    @property
    def byteoffset(self):
        return self.offset // 8

    @property
    def rawbytes(self):
        return self._rawarray

class ByteStore(ConstByteStore):
    __slots__ = ()

    def setbit(self, pos):
        assert 0 <= pos < self.bitlength
        byte, bit = divmod(self.offset + pos, 8)
        self._rawarray[byte] |= (128 >> bit)

    def unsetbit(self, pos):
        assert 0 <= pos < self.bitlength
        byte, bit = divmod(self.offset + pos, 8)
        self._rawarray[byte] &= ~(128 >> bit)

    def invertbit(self, pos):
        assert 0 <= pos < self.bitlength
        byte, bit = divmod(self.offset + pos, 8)
        self._rawarray[byte] ^= (128 >> bit)

    def setbyte(self, pos, value):
        self._rawarray[pos] = value

    def setbyteslice(self, start, end, value):
        self._rawarray[start:end] = value

def offsetcopy(s, newoffset):
    assert 0 <= newoffset < 8
    if not s.bitlength:
        raise NotImplementedError

    else:
        if newoffset == s.offset % 8:
            return ByteStore(s.getbyteslice(s.byteoffset, s.byteoffset + s.bytelength), s.bitlength, newoffset)
        newdata = []
        d = s._rawarray
        assert newoffset != s.offset % 8
        if newoffset < s.offset % 8:
            shiftleft = s.offset % 8 - newoffset
            for x in range(s.byteoffset, s.byteoffset + s.bytelength - 1):
                newdata.append(((d[x] << shiftleft) & 0xff) +
                               (d[x + 1] >> (8 - shiftleft)))
            bits_in_last_byte = (s.offset + s.bitlength) % 8
            if not bits_in_last_byte:
                bits_in_last_byte = 8
            if bits_in_last_byte > shiftleft:
                newdata.append(
                    (d[s.byteoffset + s.bytelength - 1] << shiftleft) & 0xff)
        else:
            shiftright = newoffset - s.offset % 8
            newdata.append(s.getbyte(0) >> shiftright)
            for x in range(s.byteoffset + 1, s.byteoffset + s.bytelength):
                newdata.append(((d[x - 1] << (8 - shiftright)) & 0xff) +
                               (d[x] >> shiftright))
            bits_in_last_byte = (s.offset + s.bitlength) % 8
            if not bits_in_last_byte:
                bits_in_last_byte = 8
            if bits_in_last_byte + shiftright > 8:
                newdata.append(
                    (d[s.byteoffset + s.bytelength - 1] << (8 - shiftright)) & 0xff)
        new_s = ByteStore(bytearray(newdata), s.bitlength, newoffset)
        assert new_s.offset == newoffset
        return new_s

def equal(a, b):
    a_bitlength = a.bitlength
    b_bitlength = b.bitlength
    if a_bitlength != b_bitlength:
        return False
    if not a_bitlength:
        assert b_bitlength == 0
        return True
    if (a.offset % 8) > (b.offset % 8):
        a, b = b, a
    a_bitoff = a.offset % 8
    b_bitoff = b.offset % 8
    a_byteoffset = a.byteoffset
    b_byteoffset = b.byteoffset
    a_bytelength = a.bytelength
    b_bytelength = b.bytelength
    da = a._rawarray
    db = b._rawarray
    if da is db and a.offset == b.offset:
        return True
    if a_bitoff == b_bitoff:
        bits_spare_in_last_byte = 8 - (a_bitoff + a_bitlength) % 8
        if bits_spare_in_last_byte == 8:
            bits_spare_in_last_byte = 0
        if a_bytelength == 1:
            a_val = ((da[a_byteoffset] << a_bitoff)
                     & 0xff) >> (8 - a_bitlength)
            b_val = ((db[b_byteoffset] << b_bitoff)
                     & 0xff) >> (8 - b_bitlength)
            return a_val == b_val
        if da[a_byteoffset] & (0xff >> a_bitoff) != db[b_byteoffset] & (0xff >> b_bitoff):
            return False
        b_a_offset = b_byteoffset - a_byteoffset
        for x in range(1 + a_byteoffset, a_byteoffset + a_bytelength - 1):
            if da[x] != db[b_a_offset + x]:
                return False
        return (da[a_byteoffset + a_bytelength - 1] >> bits_spare_in_last_byte ==
                db[b_byteoffset + b_bytelength - 1] >> bits_spare_in_last_byte)
    assert a_bitoff != b_bitoff
    shift = b_bitoff - a_bitoff
    if b_bytelength == 1:
        assert a_bytelength == 1
        a_val = ((da[a_byteoffset] << a_bitoff) & 0xff) >> (8 - a_bitlength)
        b_val = ((db[b_byteoffset] << b_bitoff) & 0xff) >> (8 - b_bitlength)
        return a_val == b_val
    if a_bytelength == 1:
        assert b_bytelength == 2
        a_val = ((da[a_byteoffset] << a_bitoff) & 0xff) >> (8 - a_bitlength)
        b_val = ((db[b_byteoffset] << 8) + db[b_byteoffset + 1]) << b_bitoff
        b_val &= 0xffff
        b_val >>= 16 - b_bitlength
        return a_val == b_val
    if (da[a_byteoffset] & (0xff >> a_bitoff)) >> shift != db[b_byteoffset] & (0xff >> b_bitoff):
        return False
    for x in range(1, b_bytelength - 1):
        b_val = db[b_byteoffset + x]
        a_val = ((da[a_byteoffset + x - 1] << 8) +
                 da[a_byteoffset + x]) >> shift
        a_val &= 0xff
        if a_val != b_val:
            return False
    final_b_bits = (b.offset + b_bitlength) % 8
    if not final_b_bits:
        final_b_bits = 8
    b_val = db[b_byteoffset + b_bytelength - 1] >> (8 - final_b_bits)
    final_a_bits = (a.offset + a_bitlength) % 8
    if not final_a_bits:
        final_a_bits = 8
    if b.bytelength > a_bytelength:
        assert b_bytelength == a_bytelength + 1
        a_val = da[a_byteoffset + a_bytelength - 1] >> (8 - final_a_bits)
        a_val &= 0xff >> (8 - final_b_bits)
        return a_val == b_val
    assert a_bytelength == b_bytelength
    a_val = da[a_byteoffset + a_bytelength - 2] << 8
    a_val += da[a_byteoffset + a_bytelength - 1]
    a_val >>= (8 - final_a_bits)
    a_val &= 0xff >> (8 - final_b_bits)
    return a_val == b_val

BYTE_REVERSAL_DICT = dict()

try:
    xrange
    for i in range(256):
        BYTE_REVERSAL_DICT[i] = chr(int("{0:08b}".format(i)[:-1], 2))
except NameError:
    for i in range(256):
        BYTE_REVERSAL_DICT[i] = bytes([int("{0:08b}".format(i)[:-1], 2)])
    xrange = range
    basestring = str

LEADING_OCT_CHARS = len(oct(1)) - 1

def tidy_input_string(s):
    s = ''.join(s.split()).lower()
    return s

INIT_NAMES = ('uint', 'int', 'ue', 'se', 'sie', 'uie', 'hex', 'oct', 'bin', 'bits',
              'uintbe', 'intbe', 'uintle', 'intle', 'uintne', 'intne',
              'float', 'floatbe', 'floatle', 'floatne', 'bytes', 'bool', 'pad')

REPLACEMENTS_BE = {'b': 'intbe:8', 'B': 'uintbe:8',
                   'h': 'intbe:16', 'H': 'uintbe:16',
                   'l': 'intbe:32', 'L': 'uintbe:32',
                   'q': 'intbe:64', 'Q': 'uintbe:64',
                   'f': 'floatbe:32', 'd': 'floatbe:64'}

REPLACEMENTS_LE = {'b': 'intle:8', 'B': 'uintle:8',
                   'h': 'intle:16', 'H': 'uintle:16',
                   'l': 'intle:32', 'L': 'uintle:32',
                   'q': 'intle:64', 'Q': 'uintle:64',
                   'f': 'floatle:32', 'd': 'floatle:64'}

PACK_CODE_SIZE = {'b': 1, 'B': 1, 'h': 2, 'H': 2, 'l': 4, 'L': 4,
                  'q': 8, 'Q': 8, 'f': 4, 'd': 8}

_tokenname_to_initialiser = {'hex': 'hex', '0x': 'hex', '0X': 'hex', 'oct': 'oct',
                             '0o': 'oct', '0O': 'oct', 'bin': 'bin', '0b': 'bin',
                             '0B': 'bin', 'bits': 'auto', 'bytes': 'bytes', 'pad': 'pad'}

OCT_TO_BITS = ['{0:03b}'.format(i) for i in xrange(8)]

BIT_COUNT = dict(zip(xrange(256), [bin(i).count('1') for i in xrange(256)]))

class Bits(object):
    __slots__ = ('_datastore')

    def __init__(self, length=None, offset=None, **kwargs):
        self._initialise(length, offset, **kwargs)

    def _initialise(self, length, offset, **kwargs):
        if length is not None and length < 0:
            raise CreationError("bitstring length cannot be negative.")
        if offset is not None and offset < 0:
            raise CreationError("offset must be >= 0.")
        if not kwargs:
            if length is not None and length != 0:
                data = bytearray((length + 7) // 8)
                self._setbytes_unsafe(data, length, 0)
                return
            self._setbytes_unsafe(bytearray(0), 0, 0)
            return
        k, v = kwargs.popitem()
        try:
            init_without_length_or_offset[k](self, v)
            if length is not None or offset is not None:
                raise CreationError(
                    "Cannot use length or offset with this initialiser.")
        except KeyError:
            try:
                init_with_length_only[k](self, v, length)
                if offset is not None:
                    raise CreationError(
                        "Cannot use offset with this initialiser.")
            except KeyError:
                if offset is None:
                    offset = 0
                try:
                    init_with_length_and_offset[k](self, v, length, offset)
                except KeyError:
                    raise CreationError(
                        "Unrecognised keyword '{0}' used to initialise.", k)

    def __copy__(self):
        return self

    def __lt__(self, other):
        raise TypeError("unorderable type: {0}".format(type(self).__name__))

    def __gt__(self, other):
        raise TypeError("unorderable type: {0}".format(type(self).__name__))

    def __le__(self, other):
        raise TypeError("unorderable type: {0}".format(type(self).__name__))

    def __ge__(self, other):
        raise TypeError("unorderable type: {0}".format(type(self).__name__))

    def __add__(self, bs):
        assert isinstance(bs, Bits)
        if bs.len <= self.len:
            s = self._copy()
            s._append(bs)
        else:
            s = bs._copy()
            s._prepend(self)
        return s

    def __radd__(self, bs):
        bs = self._converttobitstring(bs)
        return bs.__add__(self)

    def __getitem__(self, key):
        length = self.len
        try:
            step = key.step if key.step is not None else 1
        except AttributeError:
            if key < 0:
                key += length
            if not 0 <= key < length:
                raise IndexError("Slice index out of range.")
            return self._datastore.getbit(key)
        else:
            if step != 1:
                bs = self.__class__()
                bs._setbin_unsafe(self._getbin().__getitem__(key))
                return bs
            start, stop = 0, length
            if key.start is not None:
                start = key.start
                if key.start < 0:
                    start += stop
            if key.stop is not None:
                stop = key.stop
                if key.stop < 0:
                    stop += length
            start = max(start, 0)
            stop = min(stop, length)
            if start < stop:
                return self._slice(start, stop)
            else:
                return self.__class__()

    def __len__(self):
        return self._getlength()

    def __str__(self):
        length = self.len
        if not length:
            return ''
        if length > MAX_CHARS * 4:
            return ''.join(('0x', self._readhex(MAX_CHARS * 4, 0), '...'))
        if length < 32 and length % 4 != 0:
            return '0b' + self.bin
        if not length % 4:
            return '0x' + self.hex
        bits_at_end = length % 4
        return ''.join(('0x', self._readhex(length - bits_at_end, 0),
                        ', ', '0b',
                        self._readbin(bits_at_end, length - bits_at_end)))

    def __repr__(self):
        length = self.len
        s = self.__str__()
        lengthstring = ''
        if s.endswith('...'):
            lengthstring = " # length={0}".format(length)
        return "{0}('{1}'){2}".format(self.__class__.__name__, s, lengthstring)

    def __eq__(self, bs):
        return equal(self._datastore, bs._datastore)

    def __ne__(self, bs):
        return not self.__eq__(bs)

    def __hash__(self):
        if self.len <= 160:
            shorter = self
        else:
            shorter = self[:80] + self[-80:]
        h = 0
        for byte in shorter.tobytes():
            try:
                h = (h << 4) + ord(byte)
            except TypeError:
                h = (h << 4) + byte
            g = h & 0xf0000000
            if g & (1 << 31):
                h ^= (g >> 24)
                h ^= g
        return h % 1442968193

    def __nonzero__(self):
        return self.any(True)

    __bool__ = __nonzero__

    def _assertsanity(self):
        assert self.len >= 0
        assert 0 <= self._offset, "offset={0}".format(self._offset)
        assert (self.len + self._offset +
                7) // 8 == self._datastore.bytelength + self._datastore.byteoffset
        return True

    def _clear(self):
        self._datastore = ByteStore(bytearray(0))

    def _setbytes_safe(self, data, length=None, offset=0):
        data = bytearray(data)
        if length is None:
            length = len(data)*8 - offset
            self._datastore = ByteStore(data, length, offset)
        else:
            if length + offset > len(data) * 8:
                msg = "Not enough data present. Need {0} bits, have {1}."
                raise CreationError(msg, length + offset, len(data) * 8)
            if length == 0:
                self._datastore = ByteStore(bytearray(0))
            else:
                self._datastore = ByteStore(data, length, offset)

    def _setbytes_unsafe(self, data, length, offset):
        self._datastore = ByteStore(data[:], length, offset)
        assert self._assertsanity()

    def _readbytes(self, length, start):
        assert length % 8 == 0
        assert start + length <= self.len
        if not (start + self._offset) % 8:
            return bytes(self._datastore.getbyteslice((start + self._offset) // 8,
                                                      (start + self._offset + length) // 8))
        return self._slice(start, start + length).tobytes()

    def _getbytes(self):
        if self.len % 8:
            raise InterpretError("Cannot interpret as bytes unambiguously - "
                                 "not multiple of 8 bits.")
        return self._readbytes(self.len, 0)

    def _setuint(self, uint, length=None):
        try:
            if length is None:
                length = self._datastore.bitlength
        except AttributeError:
            pass

        if length is None or length == 0:
            raise CreationError("A non-zero length must be specified with a "
                                "uint initialiser.")
        if uint >= (1 << length):
            msg = "{0} is too large an unsigned integer for a bitstring of length {1}. "\
                  "The allowed range is [0, {2}]."
            raise CreationError(msg, uint, length, (1 << length) - 1)
        if uint < 0:
            raise CreationError(
                "uint cannot be initialsed by a negative number.")
        s = hex(uint)[2:]
        s = s.rstrip('L')
        if len(s) & 1:
            s = '0' + s
        try:
            data = bytes([int(x) for x in ubinascii.unhexlify(s)])
        except AttributeError:
            data = ubinascii.unhexlify(s)
        extrabytes = ((length + 7) // 8) - len(data)
        if extrabytes > 0:
            data = b'\x00' * extrabytes + data
        offset = 8 - (length % 8)
        if offset == 8:
            offset = 0
        self._setbytes_unsafe(bytearray(data), length, offset)

    def _readuint(self, length, start):
        if not length:
            raise InterpretError("Cannot interpret a zero length bitstring "
                                 "as an integer.")
        offset = self._offset
        startbyte = (start + offset) // 8
        endbyte = (start + offset + length - 1) // 8
        b = ubinascii.hexlify(
            bytes(self._datastore.getbyteslice(startbyte, endbyte + 1)))
        assert b
        i = int(b, 16)
        final_bits = 8 - ((start + offset + length) % 8)
        if final_bits != 8:
            i >>= final_bits
        i &= (1 << length) - 1
        return i

    def _getuint(self):
        return self._readuint(self.len, 0)

    def _setint(self, int_, length=None):
        if length is None and hasattr(self, 'len') and self.len != 0:
            length = self.len
        if length is None or length == 0:
            raise CreationError(
                "A non-zero length must be specified with an int initialiser.")
        if int_ >= (1 << (length - 1)) or int_ < -(1 << (length - 1)):
            raise CreationError("{0} is too large a signed integer for a bitstring of length {1}. "
                                "The allowed range is [{2}, {3}].", int_, length, -(
                                    1 << (length - 1)),
                                (1 << (length - 1)) - 1)
        if int_ >= 0:
            self._setuint(int_, length)
            return
        int_ += 1
        self._setuint(-int_, length)
        self._invert_all()

    def _readint(self, length, start):
        ui = self._readuint(length, start)
        if not ui >> (length - 1):
            return ui
        tmp = (~(ui - 1)) & ((1 << length) - 1)
        return -tmp

    def _getint(self):
        return self._readint(self.len, 0)

    def _setuintbe(self, uintbe, length=None):
        if length is not None and length % 8 != 0:
            raise CreationError("Big-endian integers must be whole-byte. "
                                "Length = {0} bits.", length)
        self._setuint(uintbe, length)

    def _readuintbe(self, length, start):
        if length % 8:
            raise InterpretError("Big-endian integers must be whole-byte. "
                                 "Length = {0} bits.", length)
        return self._readuint(length, start)

    def _getuintbe(self):
        return self._readuintbe(self.len, 0)

    def _setintbe(self, intbe, length=None):
        if length is not None and length % 8 != 0:
            raise CreationError("Big-endian integers must be whole-byte. "
                                "Length = {0} bits.", length)
        self._setint(intbe, length)

    def _readintbe(self, length, start):
        if length % 8:
            raise InterpretError("Big-endian integers must be whole-byte. "
                                 "Length = {0} bits.", length)
        return self._readint(length, start)

    def _getintbe(self):
        return self._readintbe(self.len, 0)

    def _setuintle(self, uintle, length=None):
        if length is not None and length % 8 != 0:
            raise CreationError("Little-endian integers must be whole-byte. "
                                "Length = {0} bits.", length)
        self._setuint(uintle, length)
        self._reversebytes(0, self.len)

    def _readuintle(self, length, start):
        if length % 8:
            raise InterpretError("Little-endian integers must be whole-byte. "
                                 "Length = {0} bits.", length)
        assert start + length <= self.len
        absolute_pos = start + self._offset
        startbyte, offset = divmod(absolute_pos, 8)
        val = 0
        if not offset:
            endbyte = (absolute_pos + length - 1) // 8
            chunksize = 4
            while endbyte - chunksize + 1 >= startbyte:
                val <<= 8 * chunksize
                val += ustruct.unpack('<L', bytes(self._datastore.getbyteslice(
                    endbyte + 1 - chunksize, endbyte + 1)))[0]
                endbyte -= chunksize
            for b in xrange(endbyte, startbyte - 1, -1):
                val <<= 8
                val += self._datastore.getbyte(b)
        else:
            data = self._slice(start, start + length)
            assert data.len % 8 == 0
            data._reversebytes(0, self.len)
            for b in bytearray(data.bytes):
                val <<= 8
                val += b
        return val

    def _getuintle(self):
        return self._readuintle(self.len, 0)

    def _setintle(self, intle, length=None):
        if length is not None and length % 8 != 0:
            raise CreationError("Little-endian integers must be whole-byte. "
                                "Length = {0} bits.", length)
        self._setint(intle, length)
        self._reversebytes(0, self.len)

    def _readintle(self, length, start):
        ui = self._readuintle(length, start)
        if not ui >> (length - 1):
            return ui
        tmp = (~(ui - 1)) & ((1 << length) - 1)
        return -tmp

    def _getintle(self):
        return self._readintle(self.len, 0)

    def _setfloat(self, f, length=None):
        if length is None and hasattr(self, 'len') and self.len != 0:
            length = self.len
        if length is None or length == 0:
            raise CreationError("A non-zero length must be specified with a "
                                "float initialiser.")
        if length == 32:
            b = ustruct.pack('>f', f)
        elif length == 64:
            b = ustruct.pack('>d', f)
        else:
            raise CreationError("floats can only be 32 or 64 bits long, "
                                "not {0} bits", length)
        self._setbytes_unsafe(bytearray(b), length, 0)

    def _readfloat(self, length, start):
        if not (start + self._offset) % 8:
            startbyte = (start + self._offset) // 8
            if length == 32:
                f, = ustruct.unpack('>f', bytes(
                    self._datastore.getbyteslice(startbyte, startbyte + 4)))
            elif length == 64:
                f, = ustruct.unpack('>d', bytes(
                    self._datastore.getbyteslice(startbyte, startbyte + 8)))
        else:
            if length == 32:
                f, = ustruct.unpack('>f', self._readbytes(32, start))
            elif length == 64:
                f, = ustruct.unpack('>d', self._readbytes(64, start))
        try:
            return f
        except NameError:
            raise InterpretError(
                "floats can only be 32 or 64 bits long, not {0} bits", length)

    def _getfloat(self):
        return self._readfloat(self.len, 0)

    def _setfloatle(self, f, length=None):
        if length is None and hasattr(self, 'len') and self.len != 0:
            length = self.len
        if length is None or length == 0:
            raise CreationError("A non-zero length must be specified with a "
                                "float initialiser.")
        if length == 32:
            b = ustruct.pack('<f', f)
        elif length == 64:
            b = ustruct.pack('<d', f)
        else:
            raise CreationError("floats can only be 32 or 64 bits long, "
                                "not {0} bits", length)
        self._setbytes_unsafe(bytearray(b), length, 0)

    def _readfloatle(self, length, start):
        startbyte, offset = divmod(start + self._offset, 8)
        if not offset:
            if length == 32:
                f, = ustruct.unpack('<f', bytes(
                    self._datastore.getbyteslice(startbyte, startbyte + 4)))
            elif length == 64:
                f, = ustruct.unpack('<d', bytes(
                    self._datastore.getbyteslice(startbyte, startbyte + 8)))
        else:
            if length == 32:
                f, = ustruct.unpack('<f', self._readbytes(32, start))
            elif length == 64:
                f, = ustruct.unpack('<d', self._readbytes(64, start))
        try:
            return f
        except NameError:
            raise InterpretError("floats can only be 32 or 64 bits long, "
                                 "not {0} bits", length)

    def _getfloatle(self):
        return self._readfloatle(self.len, 0)

    def _setue(self, i):
        if i < 0:
            raise CreationError("Cannot use negative initialiser for unsigned "
                                "exponential-Golomb.")
        if not i:
            self._setbin_unsafe('1')
            return
        tmp = i + 1
        leadingzeros = -1
        while tmp > 0:
            tmp >>= 1
            leadingzeros += 1
        remainingpart = i + 1 - (1 << leadingzeros)
        binstring = '0' * leadingzeros + '1' + Bits(uint=remainingpart,
                                                    length=leadingzeros).bin
        self._setbin_unsafe(binstring)

    def _readue(self, pos):
        oldpos = pos
        try:
            while not self[pos]:
                pos += 1
        except IndexError:
            raise ReadError("Read off end of bitstring trying to read code.")
        leadingzeros = pos - oldpos
        codenum = (1 << leadingzeros) - 1
        if leadingzeros > 0:
            if pos + leadingzeros + 1 > self.len:
                raise ReadError(
                    "Read off end of bitstring trying to read code.")
            codenum += self._readuint(leadingzeros, pos + 1)
            pos += leadingzeros + 1
        else:
            assert codenum == 0
            pos += 1
        return codenum, pos

    def _getue(self):
        try:
            value, newpos = self._readue(0)
            if value is None or newpos != self.len:
                raise ReadError
        except ReadError:
            raise InterpretError(
                "Bitstring is not a single exponential-Golomb code.")
        return value

    def _setse(self, i):
        if i > 0:
            u = (i * 2) - 1
        else:
            u = -2 * i
        self._setue(u)

    def _getse(self):
        try:
            value, newpos = self._readse(0)
            if value is None or newpos != self.len:
                raise ReadError
        except ReadError:
            raise InterpretError(
                "Bitstring is not a single exponential-Golomb code.")
        return value

    def _readse(self, pos):
        codenum, pos = self._readue(pos)
        m = (codenum + 1) // 2
        if not codenum % 2:
            return -m, pos
        else:
            return m, pos

    def _setuie(self, i):
        if i < 0:
            raise CreationError("Cannot use negative initialiser for unsigned "
                                "interleaved exponential-Golomb.")
        self._setbin_unsafe('1' if i == 0 else '0' +
                            '0'.join(bin(i + 1)[3:]) + '1')

    def _readuie(self, pos):
        try:
            codenum = 1
            while not self[pos]:
                pos += 1
                codenum <<= 1
                codenum += self[pos]
                pos += 1
            pos += 1
        except IndexError:
            raise ReadError("Read off end of bitstring trying to read code.")
        codenum -= 1
        return codenum, pos

    def _getuie(self):
        try:
            value, newpos = self._readuie(0)
            if value is None or newpos != self.len:
                raise ReadError
        except ReadError:
            raise InterpretError(
                "Bitstring is not a single interleaved exponential-Golomb code.")
        return value

    def _setsie(self, i):
        if not i:
            self._setbin_unsafe('1')
        else:
            self._setuie(abs(i))
            self._append(Bits([i < 0]))

    def _getsie(self):
        try:
            value, newpos = self._readsie(0)
            if value is None or newpos != self.len:
                raise ReadError
        except ReadError:
            raise InterpretError(
                "Bitstring is not a single interleaved exponential-Golomb code.")
        return value

    def _readsie(self, pos):
        codenum, pos = self._readuie(pos)
        if not codenum:
            return 0, pos
        try:
            if self[pos]:
                return -codenum, pos + 1
            else:
                return codenum, pos + 1
        except IndexError:
            raise ReadError("Read off end of bitstring trying to read code.")

    def _setbool(self, value):
        if value in (1, 'True'):
            self._setbytes_unsafe(bytearray(b'\x80'), 1, 0)
        elif value in (0, 'False'):
            self._setbytes_unsafe(bytearray(b'\x00'), 1, 0)
        else:
            raise CreationError('Cannot initialise boolean with {0}.', value)

    def _getbool(self):
        if self.length != 1:
            msg = "For a bool interpretation a bitstring must be 1 bit long, not {0} bits."
            raise InterpretError(msg, self.length)
        return self[0]

    def _readbool(self, pos):
        return self[pos], pos + 1

    def _setbin_safe(self, binstring):
        binstring = tidy_input_string(binstring)

        binstring = binstring.replace('0b', '')
        self._setbin_unsafe(binstring)

    def _setbin_unsafe(self, binstring):
        length = len(binstring)

        boundary = ((length + 7) // 8) * 8
        padded_binstring = binstring + '0' * (boundary - length)\
            if len(binstring) < boundary else binstring
        try:
            bytelist = [int(padded_binstring[x:x + 8], 2)
                        for x in xrange(0, len(padded_binstring), 8)]
        except ValueError:
            raise CreationError(
                "Invalid character in bin initialiser {0}.", binstring)
        self._setbytes_unsafe(bytearray(bytelist), length, 0)

    def _readbin(self, length, start):
        if not length:
            return ''
        startbyte, startoffset = divmod(start + self._offset, 8)
        endbyte = (start + self._offset + length - 1) // 8
        b = self._datastore.getbyteslice(startbyte, endbyte + 1)
        try:
            c = "{:0{}b}".format(int(ubinascii.hexlify(b), 16), 8*len(b))
        except TypeError:

            c = "{0:0{1}b}".format(
                int(ubinascii.hexlify(str(b)), 16), 8*len(b))
        return c[startoffset:startoffset + length]

    def _getbin(self):
        return self._readbin(self.len, 0)

    def _setoct(self, octstring):
        octstring = tidy_input_string(octstring)
        octstring = octstring.replace('0o', '')
        binlist = []
        for i in octstring:
            try:
                if not 0 <= int(i) < 8:
                    raise ValueError
                binlist.append(OCT_TO_BITS[int(i)])
            except ValueError:
                raise CreationError(
                    "Invalid symbol '{0}' in oct initialiser.", i)
        self._setbin_unsafe(''.join(binlist))

    def _readoct(self, length, start):
        if length % 3:
            raise InterpretError("Cannot convert to octal unambiguously - "
                                 "not multiple of 3 bits.")
        if not length:
            return ''
        end = oct(self._readuint(length, start))[LEADING_OCT_CHARS:]
        if end.endswith('L'):
            end = end[:-1]
        middle = '0' * (length // 3 - len(end))
        return middle + end

    def _getoct(self):
        return self._readoct(self.len, 0)

    def _sethex(self, hexstring):
        hexstring = tidy_input_string(hexstring)
        hexstring = hexstring.replace('0x', '')
        length = len(hexstring)
        if length % 2:
            hexstring += '0'
        try:
            try:
                data = bytearray([int(x)
                                 for x in ubinascii.unhexlify(hexstring)])
            except TypeError:
                raise NotImplementedError('Python 2.x is not supported')
                data = bytearray.fromhex(unicode(hexstring))
        except ValueError:
            raise CreationError("Invalid symbol in hex initialiser.")
        self._setbytes_unsafe(data, length * 4, 0)

    def _readhex(self, length, start):
        if length % 4:
            raise InterpretError("Cannot convert to hex unambiguously - "
                                 "not multiple of 4 bits.")
        if not length:
            return ''
        s = self._slice(start, start + length).tobytes()
        try:
            s = s.hex()
        except AttributeError:
            s = str(ubinascii.hexlify(s).decode('utf-8'))
        return s[:-1] if (length // 4) % 2 else s

    def _gethex(self):
        return self._readhex(self.len, 0)

    def _getoffset(self):
        return self._datastore.offset

    def _getlength(self):
        return self._datastore.bitlength

    def _ensureinmemory(self):
        self._setbytes_unsafe(self._datastore.getbyteslice(0, self._datastore.bytelength),
                              self.len, self._offset)

    @classmethod
    def _converttobitstring(cls, bs, offset=0):
        if isinstance(bs, Bits):
            return bs
        if isinstance(bs, basestring):
            b = cls()
            try:
                _, tokens = tokenparser(bs)
            except ValueError as e:
                raise CreationError(*e.args)
            if tokens:
                b._append(Bits._init_with_token(*tokens[0]))
                b._datastore = offsetcopy(b._datastore, offset)
                for token in tokens[1:]:
                    b._append(Bits._init_with_token(*token))
            assert b._assertsanity()
            assert b.len == 0 or b._offset == offset
            return b
        return cls(bs)

    def _copy(self):
        s_copy = self.__class__()
        s_copy._setbytes_unsafe(self._datastore.getbyteslice(0, self._datastore.bytelength),
                                self.len, self._offset)
        return s_copy

    def _slice(self, start, end):
        if end == start:
            return self.__class__()
        offset = self._offset
        startbyte, newoffset = divmod(start + offset, 8)
        endbyte = (end + offset - 1) // 8
        bs = self.__class__()
        bs._setbytes_unsafe(self._datastore.getbyteslice(
            startbyte, endbyte + 1), end - start, newoffset)
        return bs

    def _append(self, bs):
        self._datastore._appendstore(bs._datastore)

    def _prepend(self, bs):
        self._datastore._prependstore(bs._datastore)

    def _reverse(self):
        n = [BYTE_REVERSAL_DICT[b] for b in self._datastore.rawbytes]
        n.reverse()
        newoffset = 8 - (self._offset + self.len) % 8
        if newoffset == 8:
            newoffset = 0
        self._setbytes_unsafe(bytearray().join(n), self.length, newoffset)

    def _truncatestart(self, bits):
        assert 0 <= bits <= self.len
        if not bits:
            return
        if bits == self.len:
            self._clear()
            return
        bytepos, offset = divmod(self._offset + bits, 8)
        self._setbytes_unsafe(self._datastore.getbyteslice(bytepos, self._datastore.bytelength), self.len - bits,
                              offset)
        assert self._assertsanity()

    def _truncateend(self, bits):
        assert 0 <= bits <= self.len
        if not bits:
            return
        if bits == self.len:
            self._clear()
            return
        newlength_in_bytes = (self._offset + self.len - bits + 7) // 8
        self._setbytes_unsafe(self._datastore.getbyteslice(0, newlength_in_bytes), self.len - bits,
                              self._offset)
        assert self._assertsanity()

    def _insert(self, bs, pos):
        assert 0 <= pos <= self.len
        if pos > self.len // 2:
            end = self._slice(pos, self.len)
            self._truncateend(self.len - pos)
            self._append(bs)
            self._append(end)
        else:
            start = self._slice(0, pos)
            self._truncatestart(pos)
            self._prepend(bs)
            self._prepend(start)
        try:
            self._pos = pos + bs.len
        except AttributeError:
            pass
        assert self._assertsanity()

    def _overwrite(self, bs, pos):
        assert 0 <= pos < self.len
        if bs is self:
            assert pos == 0
            return
        firstbytepos = (self._offset + pos) // 8
        lastbytepos = (self._offset + pos + bs.len - 1) // 8
        bytepos, bitoffset = divmod(self._offset + pos, 8)
        if firstbytepos == lastbytepos:
            mask = ((1 << bs.len) - 1) << (8 - bs.len - bitoffset)
            self._datastore.setbyte(
                bytepos, self._datastore.getbyte(bytepos) & (~mask))
            d = offsetcopy(bs._datastore, bitoffset)
            self._datastore.setbyte(bytepos, self._datastore.getbyte(
                bytepos) | (d.getbyte(0) & mask))
        else:
            mask = (1 << (8 - bitoffset)) - 1
            self._datastore.setbyte(
                bytepos, self._datastore.getbyte(bytepos) & (~mask))
            d = offsetcopy(bs._datastore, bitoffset)
            self._datastore.setbyte(bytepos, self._datastore.getbyte(
                bytepos) | (d.getbyte(0) & mask))
            self._datastore.setbyteslice(
                firstbytepos + 1, lastbytepos, d.getbyteslice(1, lastbytepos - firstbytepos))
            bitsleft = (self._offset + pos + bs.len) % 8
            if not bitsleft:
                bitsleft = 8
            mask = (1 << (8 - bitsleft)) - 1
            self._datastore.setbyte(
                lastbytepos, self._datastore.getbyte(lastbytepos) & mask)
            self._datastore.setbyte(lastbytepos,
                                    self._datastore.getbyte(lastbytepos) | (d.getbyte(d.bytelength - 1) & ~mask))
        assert self._assertsanity()

    def _delete(self, bits, pos):
        assert 0 <= pos <= self.len
        assert pos + bits <= self.len
        if not pos:
            self._truncatestart(bits)
            return
        if pos + bits == self.len:
            self._truncateend(bits)
            return
        if pos > self.len - pos - bits:
            end = self._slice(pos + bits, self.len)
            assert self.len - pos > 0
            self._truncateend(self.len - pos)
            self._append(end)
            return
        start = self._slice(0, pos)
        self._truncatestart(pos + bits)
        self._prepend(start)
        return

    def _reversebytes(self, start, end):
        newoffset = 8 - (start % 8)
        if newoffset == 8:
            newoffset = 0
        self._datastore = offsetcopy(self._datastore, newoffset)
        toreverse = bytearray(self._datastore.getbyteslice(
            (newoffset + start) // 8, (newoffset + end) // 8))
        toreverse.reverse()
        self._datastore.setbyteslice(
            (newoffset + start) // 8, (newoffset + end) // 8, toreverse)

    def _set(self, pos):
        assert 0 <= pos < self.len
        self._datastore.setbit(pos)

    def _unset(self, pos):
        assert 0 <= pos < self.len
        self._datastore.unsetbit(pos)

    def _invert(self, pos):
        assert 0 <= pos < self.len
        self._datastore.invertbit(pos)

    def _invert_all(self):
        set = self._datastore.setbyte
        get = self._datastore.getbyte
        for p in xrange(self._datastore.byteoffset, self._datastore.byteoffset + self._datastore.bytelength):
            set(p, 256 + ~get(p))

    def _ilshift(self, n):
        assert 0 < n <= self.len
        self._append(Bits(n))
        self._truncatestart(n)
        return self

    def _irshift(self, n):
        assert 0 < n <= self.len
        self._prepend(Bits(n))
        self._truncateend(n)
        return self

    def _imul(self, n):
        assert n >= 0
        if not n:
            self._clear()
            return self
        m = 1
        old_len = self.len
        while m * 2 < n:
            self._append(self)
            m *= 2
        self._append(self[0:(n - m) * old_len])
        return self

    def _inplace_logical_helper(self, bs, f):
        self_byteoffset, self_bitoffset = divmod(self._offset, 8)
        bs_byteoffset, bs_bitoffset = divmod(bs._offset, 8)
        if bs_bitoffset != self_bitoffset:
            if not self_bitoffset:
                bs._datastore = offsetcopy(bs._datastore, 0)
            else:
                self._datastore = offsetcopy(self._datastore, bs_bitoffset)
        a = self._datastore.rawbytes
        b = bs._datastore.rawbytes
        for i in xrange(len(a)):
            a[i] = f(a[i + self_byteoffset], b[i + bs_byteoffset])
        return self

    def _readbits(self, length, start):
        return self._slice(start, start + length)

    def _validate_slice(self, start, end):
        if start is None:
            start = 0
        elif start < 0:
            start += self.len
        if end is None:
            end = self.len
        elif end < 0:
            end += self.len
        if not 0 <= end <= self.len:
            raise ValueError("end is not a valid position in the bitstring.")
        if not 0 <= start <= self.len:
            raise ValueError("start is not a valid position in the bitstring.")
        if end < start:
            raise ValueError("end must not be less than start.")
        return start, end

    def _findbytes(self, bytes_, start, end, bytealigned):
        assert self._datastore.offset == 0
        assert bytealigned is True
        bytepos = (start + 7) // 8
        found = False
        p = bytepos
        finalpos = end // 8
        increment = max(1024, len(bytes_) * 10)
        buffersize = increment + len(bytes_)
        while p < finalpos:
            buf = bytearray(self._datastore.getbyteslice(
                p, min(p + buffersize, finalpos)))
            pos = buf.find(bytes_)
            if pos != -1:
                found = True
                p += pos
                break
            p += increment
        if not found:
            return ()
        return (p * 8,)

    def _findregex(self, reg_ex, start, end, bytealigned):
        p = start
        length = len(reg_ex.pattern)
        increment = max(4096, length * 10)
        buffersize = increment + length
        while p < end:
            buf = self._readbin(min(buffersize, end - p), p)
            m = reg_ex.search(buf)
            if m:
                pos = m.start()
                if not bytealigned or (p + pos) % 8 == 0:
                    return (p + pos,)
                if bytealigned:
                    p += pos + 1
                    continue
            p += increment
        return ()

    def tobytes(self):
        d = offsetcopy(self._datastore, 0).rawbytes
        unusedbits = 8 - self.len % 8
        if unusedbits != 8:
            d[-1] &= (0xff << unusedbits)
        return bytes(d)

    def all(self, value, pos=None):
        value = bool(value)
        length = self.len
        if pos is None:
            pos = xrange(self.len)
        for p in pos:
            if p < 0:
                p += length
            if not 0 <= p < length:
                raise IndexError("Bit position {0} out of range.".format(p))
            if not self._datastore.getbit(p) is value:
                return False
        return True

    def any(self, value, pos=None):
        value = bool(value)
        length = self.len
        if pos is None:
            pos = xrange(self.len)
        for p in pos:
            if p < 0:
                p += length
            if not 0 <= p < length:
                raise IndexError("Bit position {0} out of range.".format(p))
            if self._datastore.getbit(p) is value:
                return True
        return False

    def count(self, value):
        if not self.len:
            return 0
        count = sum(BIT_COUNT[self._datastore.getbyte(i)]
                    for i in xrange(self._datastore.bytelength - 1))
        if self._offset:
            count -= BIT_COUNT[self._datastore.getbyte(0)
                               >> (8 - self._offset)]
        endbits = self._datastore.bytelength * 8 - (self._offset + self.len)
        count += BIT_COUNT[self._datastore.getbyte(
            self._datastore.bytelength - 1) >> endbits]
        return count if value else self.len - count

    if byteorder == 'little':
        _setfloatne = _setfloatle
        _readfloatne = _readfloatle
        _getfloatne = _getfloatle
        _setuintne = _setuintle
        _readuintne = _readuintle
        _getuintne = _getuintle
        _setintne = _setintle
        _readintne = _readintle
        _getintne = _getintle
    else:
        _setfloatne = _setfloat
        _readfloatne = _readfloat
        _getfloatne = _getfloat
        _setuintne = _setuintbe
        _readuintne = _readuintbe
        _getuintne = _getuintbe
        _setintne = _setintbe
        _readintne = _readintbe
        _getintne = _getintbe

    _offset = property(_getoffset)
    len = property(_getlength)
    length = property(_getlength)
    bool = property(_getbool)
    hex = property(_gethex)
    bin = property(_getbin)
    oct = property(_getoct)
    bytes = property(_getbytes)
    int = property(_getint)
    uint = property(_getuint)
    float = property(_getfloat)
    intbe = property(_getintbe)
    uintbe = property(_getuintbe)
    floatbe = property(_getfloat)
    intle = property(_getintle)
    uintle = property(_getuintle)
    floatle = property(_getfloatle)
    intne = property(_getintne)
    uintne = property(_getuintne)
    floatne = property(_getfloatne)
    ue = property(_getue)
    se = property(_getse)
    uie = property(_getuie)
    sie = property(_getsie)

name_to_read = {'uint': Bits._readuint,
                'uintle': Bits._readuintle,
                'uintbe': Bits._readuintbe,
                'uintne': Bits._readuintne,
                'int': Bits._readint,
                'intle': Bits._readintle,
                'intbe': Bits._readintbe,
                'intne': Bits._readintne,
                'float': Bits._readfloat,
                'floatbe': Bits._readfloat,
                'floatle': Bits._readfloatle,
                'floatne': Bits._readfloatne,
                'hex': Bits._readhex,
                'oct': Bits._readoct,
                'bin': Bits._readbin,
                'bits': Bits._readbits,
                'bytes': Bits._readbytes,
                'ue': Bits._readue,
                'se': Bits._readse,
                'uie': Bits._readuie,
                'sie': Bits._readsie,
                'bool': Bits._readbool,
                }

init_with_length_and_offset = {'bytes': Bits._setbytes_safe,
                               }

init_with_length_only = {'uint': Bits._setuint,
                         'int': Bits._setint,
                         'float': Bits._setfloat,
                         'uintbe': Bits._setuintbe,
                         'intbe': Bits._setintbe,
                         'floatbe': Bits._setfloat,
                         'uintle': Bits._setuintle,
                         'intle': Bits._setintle,
                         'floatle': Bits._setfloatle,
                         'uintne': Bits._setuintne,
                         'intne': Bits._setintne,
                         'floatne': Bits._setfloatne,
                         }

init_without_length_or_offset = {'bin': Bits._setbin_safe,
                                 'hex': Bits._sethex,
                                 'oct': Bits._setoct,
                                 'ue': Bits._setue,
                                 'se': Bits._setse,
                                 'uie': Bits._setuie,
                                 'sie': Bits._setsie,
                                 'bool': Bits._setbool,
                                 }

__all__ = ['Bits', 'Error', 'ReadError',
           'InterpretError', 'ByteAlignError', 'CreationError', 'bytealigned']
