#!/usr/bin/env python3
"""Read-only dex analyzer: full method/field signatures per class + invoke-site caller lookup.

Dependency-free. Reads classes*.dex inside an APK (or a raw .dex) and:

  --methods-of <class>     print every method of a class with full Java-ish signature
  --fields-of  <class>     print every field of a class with type + access flags
  --callers-of <class>#<method>
                           print every invoke site of that method: caller class+method,
                           and how many call sites
  --xref-class <class>     print every method that references the class (any invoke/field)
  --list-classes <regex>   list matching class descriptors with method/field counts

Examples:
  python dex_meta.py ref.apk --methods-of com.taobao.fleamarket.splashad.SplashAdController
  python dex_meta.py ref.apk --callers-of com.taobao.fleamarket.splashad.SplashAdController#showSplashAd

Design notes:
  * instruction walking uses the standard dex opcode->width table so we only look at
    real instruction starts (no false positives from switch payload data words).
  * everything is read-only; nothing is written next to the APK.
"""
import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------- dex primitives

NO_INDEX = 0xFFFFFFFF


def uleb128(buf, off):
    result = 0
    shift = 0
    while True:
        b = buf[off]
        off += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, off
        shift += 7


def read_string(buf, off):
    _n, p = uleb128(buf, off)
    end = buf.find(b'\x00', p)
    return buf[p:end].decode('utf-8', 'replace')


# opcode -> instruction width in 16-bit code units (dex bytecode spec).
_WIDTH = {}
for _op in (0x00, 0x01, 0x04, 0x07, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10, 0x11,
            0x12, 0x1d, 0x1e, 0x21, 0x27, 0x28):
    _WIDTH[_op] = 1
for _op in (0x02, 0x05, 0x08, 0x13, 0x15, 0x16, 0x19, 0x1a, 0x1c, 0x1f, 0x20, 0x22,
            0x23, 0x29):
    _WIDTH[_op] = 2
for _op in (0x03, 0x06, 0x09, 0x14, 0x17, 0x1b, 0x24, 0x25, 0x26, 0x2a, 0x2b, 0x2c):
    _WIDTH[_op] = 3
_WIDTH[0x18] = 5                     # const-wide (16-bit reg + 64-bit literal)
for _op in range(0x2d, 0x3e):        # cmp*, if-*, if-*z
    _WIDTH[_op] = 2
for _op in range(0x44, 0x6e):        # aget/aput, iget/iput, sget/sput
    _WIDTH[_op] = 2
for _op in range(0x6e, 0x73):        # invoke-kind
    _WIDTH[_op] = 3
for _op in range(0x74, 0x79):        # invoke-kind/range
    _WIDTH[_op] = 3
for _op in range(0x7b, 0x90):        # unop
    _WIDTH[_op] = 1
for _op in range(0x90, 0xb0):        # binop
    _WIDTH[_op] = 2
for _op in range(0xb0, 0xd0):        # binop/2addr
    _WIDTH[_op] = 1
for _op in range(0xd0, 0xd8):        # binop/lit16
    _WIDTH[_op] = 2
for _op in range(0xd8, 0xe3):        # binop/lit8
    _WIDTH[_op] = 2
_WIDTH[0xfa] = 4
_WIDTH[0xfb] = 4
_WIDTH[0xfc] = 3
_WIDTH[0xfd] = 3
_WIDTH[0xfe] = 2
_WIDTH[0xff] = 2

INVOKE_OPS = {0x6e: 'virtual', 0x6f: 'super', 0x70: 'direct', 0x71: 'static',
              0x72: 'interface', 0x74: 'virtual/range', 0x75: 'super/range',
              0x76: 'direct/range', 0x77: 'static/range', 0x78: 'interface/range'}

# diagnostic: every place a code_item walk hit an invalid opcode (should stay empty)
DESYNC = []


def iter_insns(dex, code_off):
    """Yield (pc, opcode) for real instructions in a code_item.

    Dex embeds switch / fill-array-data PAYLOAD pseudo-instructions directly in the
    insns array (ident 0x0100 packed-switch, 0x0200 sparse-switch, 0x0300
    fill-array-data). They look like a 'nop' whose high byte is 1/2/3, so a naive
    linear walk desyncs at the first switch and then reads garbage opcodes. We skip
    them by their encoded size. This is what makes the whole analyzer trustworthy.
    """
    buf = dex.buf
    insns_size = struct.unpack_from('<I', buf, code_off + 12)[0]
    base = code_off + 16
    pc = 0
    while pc < insns_size:
        unit = struct.unpack_from('<H', buf, base + pc * 2)[0]
        op = unit & 0xFF
        if op == 0x00:
            hi = (unit >> 8) & 0xFF
            if hi == 0x01:      # packed-switch-payload: ident,size,first_key,size*targets
                size = struct.unpack_from('<H', buf, base + (pc + 1) * 2)[0]
                pc += 4 + 2 * size
                continue
            if hi == 0x02:      # sparse-switch-payload: ident,size,size*keys,size*targets
                size = struct.unpack_from('<H', buf, base + (pc + 1) * 2)[0]
                pc += 2 + 4 * size
                continue
            if hi == 0x03:      # fill-array-data-payload: ident,elem_width,size(u32),data
                ew = struct.unpack_from('<H', buf, base + (pc + 1) * 2)[0]
                n = struct.unpack_from('<I', buf, base + (pc + 2) * 2)[0]
                pc += 4 + (n * ew + 1) // 2
                continue
            yield pc, 0x00
            pc += 1
            continue
        w = _WIDTH.get(op)
        if w is None:           # invalid/free opcode: stop rather than emit garbage
            DESYNC.append((dex.name, code_off, pc, op))
            return
        yield pc, op
        pc += w


class Dex:
    def __init__(self, name, buf):
        self.name = name
        self.buf = buf
        (self.string_ids_size, self.string_ids_off,
         self.type_ids_size, self.type_ids_off,
         self.proto_ids_size, self.proto_ids_off,
         self.field_ids_size, self.field_ids_off,
         self.method_ids_size, self.method_ids_off,
         self.class_defs_size, self.class_defs_off) = struct.unpack_from('<12I', buf, 0x38)
        self._s_cache = {}
        self._t_cache = {}
        self._p_cache = {}

    # -- ids
    def string(self, idx):
        if idx in self._s_cache:
            return self._s_cache[idx]
        off = struct.unpack_from('<I', self.buf, self.string_ids_off + idx * 4)[0]
        v = read_string(self.buf, off)
        self._s_cache[idx] = v
        return v

    def type_desc(self, idx):
        if idx == NO_INDEX:
            return '?'
        if idx in self._t_cache:
            return self._t_cache[idx]
        s = self.string(struct.unpack_from('<I', self.buf, self.type_ids_off + idx * 4)[0])
        self._t_cache[idx] = s
        return s

    def proto(self, idx):
        if idx in self._p_cache:
            return self._p_cache[idx]
        ret_idx, params_off = struct.unpack_from('<II', self.buf, self.proto_ids_off + idx * 12 + 4)
        params = []
        if params_off:
            size = struct.unpack_from('<I', self.buf, params_off)[0]
            for i in range(size):
                tidx = struct.unpack_from('<H', self.buf, params_off + 4 + i * 2)[0]
                params.append(self.type_desc(tidx))
        v = (self.type_desc(ret_idx), params)
        self._p_cache[idx] = v
        return v

    def method(self, idx):
        cls_idx, proto_idx, name_idx = struct.unpack_from(
            '<HHI', self.buf, self.method_ids_off + idx * 8)
        ret, params = self.proto(proto_idx)
        return self.type_desc(cls_idx), self.string(name_idx), ret, params

    def field(self, idx):
        cls_idx, type_idx, name_idx = struct.unpack_from(
            '<HHI', self.buf, self.field_ids_off + idx * 8)
        return self.type_desc(cls_idx), self.string(name_idx), self.type_desc(type_idx)

    # -- classes
    def classes(self):
        """yield (class_desc, access_flags, [method_idx...], class_data_off)"""
        for i in range(self.class_defs_size):
            base = self.class_defs_off + i * 32
            class_idx, access, _sup, _if, _src, _ann, cdata_off, _sv = struct.unpack_from(
                '<IIIIIIII', self.buf, base)
            yield self.type_desc(class_idx), access, cdata_off

    def class_data(self, cdata_off):
        """parse class_data_item -> (static_fields, instance_fields, direct_methods, virtual_methods).

        Fields are (field_idx, access_flags); methods are (method_idx, access_flags, code_off).
        static/instance fields and direct/virtual methods are FOUR independent diff-encoded
        lists, each with its own accumulator reset to 0 (dexlib semantics) - see dex spec
        'class_data_item'.
        """
        if not cdata_off:
            return [], [], [], []
        p = cdata_off
        sf, p = uleb128(self.buf, p)
        inf, p = uleb128(self.buf, p)
        dm, p = uleb128(self.buf, p)
        vm, p = uleb128(self.buf, p)

        def fields(n):
            nonlocal p
            out = []
            idx = 0
            for _ in range(n):
                d, p = uleb128(self.buf, p)
                a, p = uleb128(self.buf, p)
                idx += d
                out.append((idx, a))
            return out

        def methods(n):
            nonlocal p
            out = []
            idx = 0
            for _ in range(n):
                d, p = uleb128(self.buf, p)
                a, p = uleb128(self.buf, p)
                c, p = uleb128(self.buf, p)
                idx += d
                out.append((idx, a, c))
            return out

        sf_fields = fields(sf)
        inf_fields = fields(inf)
        dm_methods = methods(dm)
        vm_methods = methods(vm)
        return sf_fields, inf_fields, dm_methods, vm_methods

    def class_methods(self, cdata_off):
        """yield (method_idx, access_flags, code_off) for direct then virtual methods"""
        _sf, _inf, dm, vm = self.class_data(cdata_off)
        for row in dm:
            yield row
        for row in vm:
            yield row


# ---------------------------------------------------------------- pretty printing


def fmt_type(desc):
    if not desc:
        return '?'
    arr = 0
    while desc.startswith('['):
        arr += 1
        desc = desc[1:]
    if desc.startswith('L') and desc.endswith(';'):
        base = desc[1:-1].replace('/', '.')
    else:
        base = desc
    return base + '[]' * arr


def fmt_method(owner, name, ret, params, access=0, idx=None):
    flags = []
    if access & 0x8:
        flags.append('static')
    if access & 0x1:
        flags.append('public')
    if access & 0x2:
        flags.append('private')
    if access & 0x4:
        flags.append('protected')
    if access & 0x10:
        flags.append('final')
    if access & 0x400:
        flags.append('abstract')
    if access & 0x1000:
        flags.append('synthetic')
    fl = ('[' + ' '.join(flags) + '] ') if flags else ''
    return f"{fl}{fmt_type(ret)} {owner}.{name}({', '.join(fmt_type(p) for p in params)})"


# ---------------------------------------------------------------- analysis passes


def load(apk):
    dexes = []
    if str(apk).lower().endswith('.dex'):
        dexes.append(Dex(apk.name, apk.read_bytes()))
    else:
        with zipfile.ZipFile(apk) as z:
            for n in sorted(x for x in z.namelist() if x.endswith('.dex')):
                dexes.append(Dex(n, z.read(n)))
    return dexes


def resolve_class(dexes, want):
    """find (dex, class_desc, cdata_off, access) by simple or full name."""
    want_dot = want.replace('$', '$')
    hits = []
    for d in dexes:
        for desc, access, cdata in d.classes():
            full = desc[1:-1].replace('/', '.') if desc.startswith('L') else desc
            if full == want_dot or full.endswith('.' + want_dot) or full.split('.')[-1] == want_dot:
                hits.append((d, desc, cdata, full))
    return hits


def count_invokes(dex, code_off, target_mid, collect=None, caller=None):
    """walk the code_item at code_off; count/collect invoke sites of target_mid."""
    if not code_off:
        return 0
    insns_size = struct.unpack_from('<I', dex.buf, code_off + 12)[0]
    if insns_size == 0:
        return 0
    base = code_off + 16
    n = 0
    for pc, op in iter_insns(dex, code_off):
        if op in INVOKE_OPS and pc + 2 < insns_size:
            mid = struct.unpack_from('<H', dex.buf, base + (pc + 1) * 2)[0]
            if mid == target_mid:
                n += 1
                if collect is not None:
                    collect.append((caller, INVOKE_OPS[op]))
    return n


def cmd_methods_of(dexes, args):
    for d in dexes:
        for desc, access, cdata in d.classes():
            full = desc[1:-1].replace('/', '.')
            if full == args.methods_of or full.split('.')[-1] == args.methods_of:
                print(f"# {full}   [{d.name}] access=0x{access:x} class_data=0x{cdata:x}")
                rows = []
                for midx, macc, code in d.class_methods(cdata):
                    _c, name, ret, params = d.method(midx)
                    rows.append((name, fmt_method(full, name, ret, params, macc), bool(code)))
                for _n, line, has_code in sorted(rows):
                    print(('  ' + ('CODE ' if has_code else 'ABST ') + line))


def cmd_fields_of(dexes, args):
    for d in dexes:
        for desc, access, cdata in d.classes():
            full = desc[1:-1].replace('/', '.')
            if full == args.fields_of or full.split('.')[-1] == args.fields_of:
                print(f"# {full}   [{d.name}]")
                if not cdata:
                    continue
                _sf, _inf, _dm, _vm = [], [], [], []
                sf_fields, inf_fields, _dm, _vm = d.class_data(cdata)
                for fidx, af in sf_fields + inf_fields:
                    _c, name, ftype = d.field(fidx)
                    kind = 'static' if af & 0x8 else 'instance'
                    print(f"  [{kind}] {fmt_type(ftype)} {name}")


def _method_id_index(dexes, spec):
    """spec = 'com.a.B#name' -> (dex, midx, resolved descriptor) ; name may be '*'"""
    if '#' not in spec:
        raise SystemExit('need <class>#<method>')
    cls, meth = spec.split('#', 1)
    out = []
    for d in dexes:
        for i in range(d.method_ids_size):
            c, name, ret, params = d.method(i)
            full = c[1:-1].replace('/', '.') if c.startswith('L') else c
            if full != cls and full.split('.')[-1] != cls:
                continue
            if name != meth and meth != '*':
                continue
            out.append((d, i, full, name, ret, params))
    return out


def cmd_callers_of(dexes, specs):
    """Single pass over every code_item, resolving ALL requested targets at once.

    A method defined in dex X may be invoked from dex Y (Y has its own method_ids
    reference table), so we scan every dex and match against that dex's own
    method_idx. One pass instead of one pass per target.
    """
    # per dex: method_idx -> list of (label, full, name, ret, params)
    per_dex = {}
    for spec in specs:
        for d, i, full, name, ret, params in _method_id_index(dexes, spec):
            per_dex.setdefault(d.name, (d, {}))[1].setdefault(i, []).append(
                (spec, full, name, ret, params))
    if not per_dex:
        print(f'# no method_id matched any of: {", ".join(specs)}')
        return

    results = {}          # (dex_name, midx, spec) -> list of (caller_tuple, kind)
    for dex_name, (d, wanted) in per_dex.items():
        for desc, access, cdata in d.classes():
            caller_full = desc[1:-1].replace('/', '.')
            for cmidx, macc, code in d.class_methods(cdata):
                if not code:
                    continue
                insns_size = struct.unpack_from('<I', d.buf, code + 12)[0]
                base = code + 16
                caller_tuple = None
                for pc, op in iter_insns(d, code):
                    if op not in INVOKE_OPS or pc + 2 >= insns_size:
                        continue
                    mid = struct.unpack_from('<H', d.buf, base + (pc + 1) * 2)[0]
                    if mid not in wanted:
                        continue
                    if caller_tuple is None:
                        _c, cname, cret, cparams = d.method(cmidx)
                        caller_tuple = (caller_full, cname, cret, cparams, macc)
                    for (spec, _f, _n, _r, _p) in wanted[mid]:
                        results.setdefault((dex_name, mid, spec), []).append(
                            (caller_tuple, INVOKE_OPS[op]))

    for spec in specs:
        print(f'# ======== TARGET {spec}')
        found_any = False
        for (dex_name, mid, s2), hits in sorted(results.items()):
            if s2 != spec:
                continue
            found_any = True
            full, name, ret, params = per_dex[dex_name][1][mid][0][1:]
            print(f'# == {fmt_method(full, name, ret, params)}  [method_idx={mid} in {dex_name}]')
            print(f'#    call sites: {len(hits)} in '
                  f'{len({(h[0][0], h[0][1]) for h in hits})} caller method(s)')
            seen = set()
            for (cfull, cname, cret, cparams, cmacc), kind in hits:
                key = (cfull, cname, tuple(cparams))
                if key in seen:
                    continue
                seen.add(key)
                print('  ' + fmt_method(cfull, cname, cret, cparams, cmacc)
                      + f'   <- invoke-{kind}')
        if not found_any:
            print(f'#    NO CALLER (method_id exists only as an unresolved reference)')


def cmd_xref_class(dexes, args):
    """every method that mentions the class descriptor as an invoke target or field owner."""
    want = args.xref_class
    if not want.startswith('L'):
        want = 'L' + want.replace('.', '/') + ';'
    out = []
    for d in dexes:
        field_owners = set()
        for i in range(d.field_ids_size):
            c, name, ftype = d.field(i)
            if c == want:
                field_owners.add(i)
        for desc, access, cdata in d.classes():
            caller_full = desc[1:-1].replace('/', '.')
            for cmidx, macc, code in d.class_methods(cdata):
                if not code:
                    continue
                insns_size = struct.unpack_from('<I', d.buf, code + 12)[0]
                base = code + 16
                kinds = set()
                for pc, op in iter_insns(d, code):
                    if op in INVOKE_OPS and pc + 2 < insns_size:
                        mid = struct.unpack_from('<H', d.buf, base + (pc + 1) * 2)[0]
                        c, _n, _r, _p = d.method(mid)
                        if c == want:
                            kinds.add('invoke')
                    if 0x52 <= op <= 0x6d and pc + 1 < insns_size:
                        fid = struct.unpack_from('<H', d.buf, base + (pc + 1) * 2)[0]
                        if fid in field_owners:
                            kinds.add('field')
                if kinds:
                    _c, cname, cret, cparams = d.method(cmidx)
                    out.append((caller_full, fmt_method(caller_full, cname, cret, cparams, macc),
                                ','.join(sorted(kinds))))
    print(f"# {len(out)} method(s) reference {want}")
    for _f, line, k in out:
        print(f'  ({k}) {line}')


def cmd_string_refs(dexes, args):
    """find every method that loads one of the given string literals (const-string)."""
    wants = set(args.string_refs.split(','))
    for d in dexes:
        # string_idx -> value is d.string(i); build reverse lazily by probing used indices
        used = {}
        for desc, access, cdata in d.classes():
            caller_full = desc[1:-1].replace('/', '.')
            for cmidx, macc, code in d.class_methods(cdata):
                if not code:
                    continue
                insns_size = struct.unpack_from('<I', d.buf, code + 12)[0]
                base = code + 16
                found = []
                for pc, op in iter_insns(d, code):
                    if op == 0x1a and pc + 1 < insns_size:
                        sidx = struct.unpack_from('<H', d.buf, base + (pc + 1) * 2)[0]
                        if sidx not in used:
                            used[sidx] = d.string(sidx)
                        if used[sidx] in wants:
                            found.append(used[sidx])
                    elif op == 0x1b and pc + 2 < insns_size:
                        sidx = struct.unpack_from('<I', d.buf, base + (pc + 1) * 2)[0]
                        if sidx not in used:
                            used[sidx] = d.string(sidx)
                        if used[sidx] in wants:
                            found.append(used[sidx])
                if found:
                    _c, cname, cret, cparams = d.method(cmidx)
                    print(f"  \"{','.join(sorted(set(found)))}\"  <- "
                          f"{fmt_method(caller_full, cname, cret, cparams, macc)}")


def cmd_list_classes(dexes, args):
    rx = re.compile(args.list_classes)
    n = 0
    for d in dexes:
        for desc, access, cdata in d.classes():
            full = desc[1:-1].replace('/', '.')
            if rx.search(full):
                mc = sum(1 for _ in d.class_methods(cdata)) if cdata else 0
                print(f'{full}\t[{d.name}]\tmethods={mc}')
                n += 1
    print(f'# {n} class(es)', file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--methods-of')
    ap.add_argument('--fields-of')
    ap.add_argument('--callers-of')
    ap.add_argument('--xref-class')
    ap.add_argument('--string-refs')
    ap.add_argument('--list-classes')
    args = ap.parse_args()

    dexes = load(Path(args.target))
    print(f'# loaded {len(dexes)} dex, '
          f'{sum(d.class_defs_size for d in dexes)} classes, '
          f'{sum(d.method_ids_size for d in dexes)} method ids', file=sys.stderr)

    did = False
    if args.methods_of:
        for spec in args.methods_of.split(','):
            args.methods_of = spec
            cmd_methods_of(dexes, args)
        did = True
    if args.fields_of:
        for spec in args.fields_of.split(','):
            args.fields_of = spec
            cmd_fields_of(dexes, args)
        did = True
    if args.callers_of:
        cmd_callers_of(dexes, args.callers_of.split(','))
        did = True
    if args.xref_class:
        for spec in args.xref_class.split(','):
            args.xref_class = spec
            cmd_xref_class(dexes, args)
        did = True
    if args.list_classes:
        cmd_list_classes(dexes, args); did = True
    if args.string_refs:
        cmd_string_refs(dexes, args); did = True
    if not did:
        ap.print_help()


if __name__ == '__main__':
    main()
