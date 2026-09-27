#!/usr/bin/env python3
"""Cross-dex caller finder.

Parses every classes*.dex in an APK, walks each method's code_item instruction
stream (proper opcode width table, payloads handled), and records every
invoke-kind / invoke-custom / invoke-polymorphic call site.

Modes:
  --dump FILE           write "callerClass#callerMethod\tcalleeClass#calleeName(proto)" TSV
  --to    REGEX         print call sites whose callee matches REGEX (class#name)
  --from  REGEX         print call sites whose caller matches REGEX
  --class REGEX         print all methods defined by classes matching REGEX

Examples:
  python tools/dex_callers.py app.apk --to 'BootImageInfo;->getFromType'
  python tools/dex_callers.py app.apk --from 'BootImageDataMgr' --to ';'
"""
import argparse
import re
import struct
import sys
import zipfile
from pathlib import Path

# ---------------------------------------------------------------- dex readers

def uleb128(buf, off):
    r = 0
    s = 0
    while True:
        b = buf[off]
        off += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80):
            return r, off
        s += 7


class Dex:
    def __init__(self, name, buf):
        self.name = name
        self.buf = buf
        self.magic = buf[:8]
        if buf[:4] != b'dex\n':
            # e.g. "cdex" (CompactDex) or a stripped/protected container
            self.class_defs_size = 0
            self.class_defs_off = 0
            (self.string_ids_size, self.string_ids_off,
             self.type_ids_size, self.type_ids_off,
             self.proto_ids_size, self.proto_ids_off,
             self.field_ids_size, self.field_ids_off,
             self.method_ids_size, self.method_ids_off) = (0,) * 10
            return
        (self.string_ids_size, self.string_ids_off,
         self.type_ids_size, self.type_ids_off,
         self.proto_ids_size, self.proto_ids_off,
         self.field_ids_size, self.field_ids_off,
         self.method_ids_size, self.method_ids_off) = struct.unpack_from('<10I', buf, 0x38)
        self.class_defs_size, self.class_defs_off = struct.unpack_from('<II', buf, 0x60)

    def string(self, idx):
        off = struct.unpack_from('<I', self.buf, self.string_ids_off + idx * 4)[0]
        n, p = uleb128(self.buf, off)
        return self.buf[p:p + n].decode('utf-8', 'replace')

    def type_desc(self, idx):
        return self.string(struct.unpack_from('<I', self.buf, self.type_ids_off + idx * 4)[0])

    def proto_shorty_and_desc(self, idx):
        # proto_id_item: shorty_idx(u4) return_type_idx(u4) parameters_off(u4) = 12 bytes
        shorty_idx, ret_idx, params_off = struct.unpack_from('<III', self.buf, self.proto_ids_off + idx * 12)
        ret = self.type_desc(ret_idx)
        params = []
        if params_off:
            size = struct.unpack_from('<I', self.buf, params_off)[0]
            for i in range(size):
                t = struct.unpack_from('<H', self.buf, params_off + 4 + i * 2)[0]
                params.append(self.type_desc(t))
        return ret, params

    def method(self, idx):
        class_idx, proto_idx, name_idx = struct.unpack_from('<HHI', self.buf, self.method_ids_off + idx * 8)
        cls = self.type_desc(class_idx)
        name = self.string(name_idx)
        ret, params = self.proto_shorty_and_desc(proto_idx)
        return cls, name, ret, params


# ------------------------------------------------------- instruction widths

def build_widths():
    w = [1] * 256
    for op, size in {
        0x02: 2, 0x03: 3, 0x05: 2, 0x06: 3, 0x08: 2, 0x09: 3,
        0x13: 2, 0x14: 3, 0x15: 2, 0x16: 2, 0x17: 3, 0x18: 5, 0x19: 2,
        0x1a: 2, 0x1b: 3, 0x1c: 2, 0x1f: 2, 0x20: 2, 0x22: 2, 0x23: 2,
        0x24: 3, 0x25: 3, 0x26: 3, 0x29: 2, 0x2a: 3, 0x2b: 3, 0x2c: 3,
        0x6e: 3, 0x6f: 3, 0x70: 3, 0x71: 3, 0x72: 3,
        0x74: 3, 0x75: 3, 0x76: 3, 0x77: 3, 0x78: 3,
        0xfa: 4, 0xfb: 4, 0xfc: 3, 0xfd: 3, 0xfe: 2, 0xff: 2,
    }.items():
        w[op] = size
    # 23x binops 0x2d..0x31 and 0x90..0xaf
    for op in list(range(0x2d, 0x32)) + list(range(0x90, 0xb0)) + list(range(0x44, 0x52)):
        w[op] = 2
    for op in list(range(0x32, 0x3e)):          # if-test / if-testz (22t/21t)
        w[op] = 2
    for op in list(range(0x52, 0x60)) + list(range(0x60, 0x6e)):  # iget/iput/sget/sput 22c/21c
        w[op] = 2
    for op in list(range(0xd0, 0xd8)):          # binop/lit16 22s
        w[op] = 2
    for op in list(range(0xd8, 0xe3)):          # binop/lit8 22b
        w[op] = 2
    return w


WIDTH = build_widths()
INVOKE_KIND = {0x6e, 0x6f, 0x70, 0x71, 0x72, 0x74, 0x75, 0x76, 0x77, 0x78}


def payload_size(buf, off, insns_off, insns_size_units):
    """off/insns_off are byte offsets; returns instruction width in code units."""
    ident = struct.unpack_from('<H', buf, off)[0]
    if ident == 0x0100:      # packed-switch payload
        size = struct.unpack_from('<H', buf, off + 2)[0]
        return 4 + size * 2
    if ident == 0x0200:      # sparse-switch payload
        size = struct.unpack_from('<H', buf, off + 2)[0]
        return 2 + size * 4
    if ident == 0x0300:      # fill-array-data payload
        elem_width = struct.unpack_from('<H', buf, off + 2)[0]
        size = struct.unpack_from('<I', buf, off + 4)[0]
        total_bytes = elem_width * size
        return 4 + (total_bytes + 1) // 2
    return 1


def iter_code_items(dex):
    """Yield (class_desc, method_name, proto_str, code_off, insns_off, insns_size)."""
    buf = dex.buf
    for i in range(dex.class_defs_size):
        base = dex.class_defs_off + i * 32
        class_idx = struct.unpack_from('<I', buf, base)[0]
        class_data_off = struct.unpack_from('<I', buf, base + 24)[0]
        if class_data_off == 0:
            continue
        cls = dex.type_desc(class_idx)
        off = class_data_off
        static_fields, off = uleb128(buf, off)
        instance_fields, off = uleb128(buf, off)
        direct_methods, off = uleb128(buf, off)
        virtual_methods, off = uleb128(buf, off)
        for _ in range(static_fields):
            _, off = uleb128(buf, off)
            _, off = uleb128(buf, off)
        for _ in range(instance_fields):
            _, off = uleb128(buf, off)
            _, off = uleb128(buf, off)
        # direct_methods and virtual_methods are two independent diff chains,
        # each restarting from 0.
        for count in (direct_methods, virtual_methods):
            method_idx = 0
            for _ in range(count):
                diff, off = uleb128(buf, off)
                method_idx += diff
                _access, off = uleb128(buf, off)
                code_off, off = uleb128(buf, off)
                if code_off == 0 or method_idx >= dex.method_ids_size:
                    continue
                _mcls, mname, ret, params = dex.method(method_idx)
                code = struct.unpack_from('<HHHHII', buf, code_off)
                insns_size = code[5]
                insns_off = code_off + 16
                proto = '(' + ''.join(params) + ')' + ret
                yield cls, mname, proto, code_off, insns_off, insns_size


def scan(dex, on_call):
    buf = dex.buf
    for cls, mname, proto, code_off, insns_off, insns_size in iter_code_items(dex):
        i = 0
        end_byte = insns_off + insns_size * 2
        while i < insns_size:
            byte_off = insns_off + i * 2
            if byte_off + 2 > end_byte:
                break
            unit = struct.unpack_from('<H', buf, byte_off)[0]
            op = unit & 0xFF
            if op == 0x00 and (unit >> 8) != 0:
                i += payload_size(buf, byte_off, insns_off, insns_size)
                continue
            if op in INVOKE_KIND and byte_off + 4 <= end_byte:
                midx = struct.unpack_from('<H', buf, byte_off + 2)[0]
                if midx < dex.method_ids_size:
                    on_call(cls, mname, proto, dex.method(midx))
            if op == 0xfa or op == 0xfb:            # 45cc / 4rcc: proto after method
                i += WIDTH[op]
            else:
                i += WIDTH[op]


# ------------------------------------------------------------------- driver

def iter_dex(apk):
    if apk.suffix.lower() == '.dex':
        yield Dex(apk.name, apk.read_bytes())
        return
    with zipfile.ZipFile(apk) as z:
        for n in sorted(x for x in z.namelist() if x.endswith('.dex')):
            yield Dex(n, z.read(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--dump')
    ap.add_argument('--to', action='append', default=[])
    ap.add_argument('--from', dest='from_re', action='append', default=[])
    ap.add_argument('--skip-callee', action='append', default=[],
                    help='regex; call sites whose callee class matches are not dumped')
    ap.add_argument('--limit', type=int, default=500)
    args = ap.parse_args()

    to_res = [re.compile(p) for p in args.to]
    from_res = [re.compile(p) for p in args.from_re]
    skip_res = [re.compile(p) for p in args.skip_callee]
    apk = Path(args.target)
    dumped = open(args.dump, 'w', encoding='utf-8') if args.dump else None
    shown = 0
    total = 0

    def on_call(cc, cm, cp, callee):
        nonlocal shown, total
        total += 1
        kcls, kname, kret, kparams = callee
        if skip_res and any(r.search(kcls) for r in skip_res):
            return
        caller = f'{cc}#{cm}'
        callee_s = f'{kcls}#{kname}(' + ''.join(kparams) + f'){kret}'
        if dumped:
            dumped.write(f'{caller}\t{callee_s}\n')
        if to_res and not any(r.search(f'{kcls}#{kname}') for r in to_res):
            return
        if from_res and not any(r.search(caller) for r in from_res):
            return
        if shown < args.limit:
            print(f'{caller}\t->\t{callee_s}')
        shown += 1

    for dex in iter_dex(apk):
        if dex.magic[:4] != b'dex\n':
            print(f'# SKIP non-standard dex {dex.name} magic={dex.magic!r}', file=sys.stderr)
            continue
        scan(dex, on_call)
    if dumped:
        dumped.close()
    print(f'# total call sites={total} matched={shown}', file=sys.stderr)


if __name__ == '__main__':
    main()
