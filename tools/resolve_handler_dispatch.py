#!/usr/bin/env python3
"""Resolve Stonekeep cell+0x07 dispatch handlers through LE fixups.

Evidence policy:
- SAV files supply handler IDs only.
- SK.EXE LE metadata/fixup records supply dispatch slot -> target mapping.
- No raw 32-bit table value is promoted to a runtime address without a matching
  internal OFF32 fixup.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict

CELL_SIZE = 0x15
DISPATCH_OBJECT = 3
DISPATCH_OBJECT_OFFSET = 0xF16A
OFF32 = 0x07
TARGET_INTERNAL = 0x00
TFLAG_OFF32 = 0x10
TFLAG_OBJ16 = 0x40
SFLAG_LIST = 0x20

@dataclass(frozen=True)
class LEObject:
    size: int
    base: int
    flags: int
    map_index: int
    map_size: int

class LEError(ValueError):
    pass

def u16(b: bytes, o: int) -> int: return struct.unpack_from('<H', b, o)[0]
def i16(b: bytes, o: int) -> int: return struct.unpack_from('<h', b, o)[0]
def u32(b: bytes, o: int) -> int: return struct.unpack_from('<I', b, o)[0]

def handler_ids(path: Path):
    data = path.read_bytes()
    rows, cols = struct.unpack_from('<HH', data, 7)
    ids = set()
    for i in range(rows * cols):
        h = struct.unpack_from('<h', data, 11 + i * CELL_SIZE + 7)[0]
        if h:
            ids.add(h)
    return rows, cols, sorted(ids)

def parse_le(data: bytes):
    if len(data) < 0x40 or data[:2] != b'MZ':
        raise LEError('missing MZ header')
    le = u32(data, 0x3C)
    if data[le:le+2] != b'LE':
        raise LEError('missing LE header')
    num_pages = u32(data, le + 20)
    page_size = u32(data, le + 40)
    objtab = le + u32(data, le + 64)
    num_objects = u32(data, le + 68)
    objmap = le + u32(data, le + 72)
    fixpage = le + u32(data, le + 104)
    fixrec = le + u32(data, le + 108)
    page_data = u32(data, le + 128)
    objects = []
    for i in range(num_objects):
        size, base, flags, map_index, map_size, _ = struct.unpack_from('<6I', data, objtab + i*24)
        objects.append(LEObject(size, base, flags, map_index, map_size))
    fixmap = list(struct.unpack_from(f'<{num_pages+1}I', data, fixpage))
    return {
        'le_offset': le, 'num_pages': num_pages, 'page_size': page_size,
        'objmap': objmap, 'fixrec': fixrec, 'page_data': page_data,
        'objects': objects, 'fixmap': fixmap,
    }

def page_file_offset(data: bytes, leinfo, zero_page: int) -> int:
    p = leinfo['objmap'] + zero_page*4
    e = data[p:p+4]
    if len(e) != 4 or e[3] != 0:
        raise LEError(f'non-valid/unsupported LE page {zero_page+1}')
    page_num = (e[0] << 16) | (e[1] << 8) | e[2]
    if page_num <= 0:
        raise LEError(f'invalid physical page number for LE page {zero_page+1}')
    return leinfo['page_data'] + (page_num - 1) * leinfo['page_size']

def parse_fixup_page(data: bytes, leinfo, zero_page: int):
    fm = leinfo['fixmap']; fr = leinfo['fixrec']
    pos, end = fr + fm[zero_page], fr + fm[zero_page+1]
    out = []
    while pos < end:
        start = pos
        stype, flags = data[pos], data[pos+1]; pos += 2
        if stype & SFLAG_LIST:
            count = data[pos]; pos += 1
            src_single = None
        else:
            count = None
            src_single = i16(data, pos); pos += 2
        if flags & TFLAG_OBJ16:
            target_obj = u16(data, pos); pos += 2
        else:
            target_obj = data[pos]; pos += 1
        target_kind = flags & 0x03
        target_off = None
        if target_kind == TARGET_INTERNAL:
            if (stype & 0x0F) != 0x02:
                if flags & TFLAG_OFF32:
                    target_off = u32(data, pos); pos += 4
                else:
                    target_off = u16(data, pos); pos += 2
        elif target_kind == 0x01:
            pos += 2 if (flags & TFLAG_OBJ16) else 1
            if flags & 0x80: pos += 1
            elif flags & TFLAG_OFF32: pos += 4
            else: pos += 2
            if flags & 0x04: pos += 4
        elif target_kind == 0x02:
            pos += 2 if (flags & TFLAG_OBJ16) else 1
            pos += 4 if (flags & TFLAG_OFF32) else 2
            if flags & 0x04: pos += 4
        else:
            pos += 2 if (flags & TFLAG_OBJ16) else 1
            if flags & 0x04: pos += 4
        if stype & SFLAG_LIST:
            srcs = list(struct.unpack_from(f'<{count}h', data, pos)); pos += 2*count
        else:
            srcs = [src_single]
        if pos > end:
            raise LEError(f'fixup record overruns page {zero_page+1}')
        out.append({
            'source_type': stype, 'flags': flags, 'source_offsets': srcs,
            'target_kind': target_kind, 'target_object': target_obj,
            'target_offset': target_off, 'record_hex': data[start:pos].hex(),
        })
    if pos != end:
        raise LEError(f'fixup page {zero_page+1} parse mismatch')
    return out

def object_page(obj: LEObject, object_offset: int, page_size: int):
    if object_offset < 0 or object_offset >= obj.size:
        raise LEError(f'object offset 0x{object_offset:X} outside object')
    return (obj.map_index - 1) + object_offset // page_size, object_offset % page_size

def object_raw_file_offset(data: bytes, leinfo, obj: LEObject, object_offset: int):
    zp, within = object_page(obj, object_offset, leinfo['page_size'])
    return page_file_offset(data, leinfo, zp) + within

def build(exe_path: Path, saves: list[Path]):
    exe = exe_path.read_bytes(); le = parse_le(exe); objects = le['objects']
    if len(objects) < DISPATCH_OBJECT:
        raise LEError('dispatch object missing')
    dispatch_obj = objects[DISPATCH_OBJECT-1]
    all_ids = set(); by_save = {}
    for p in saves:
        rows, cols, ids = handler_ids(p); all_ids.update(ids)
        by_save[str(p)] = {
            'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
            'rows': rows, 'columns': cols, 'nondefault_handler_ids': ids,
        }
    page_cache = {}
    entries = {}
    errors = []
    for hid in sorted(all_ids):
        slot_off = DISPATCH_OBJECT_OFFSET + hid*4
        zp, src_off = object_page(dispatch_obj, slot_off, le['page_size'])
        if zp not in page_cache:
            by_src = defaultdict(list)
            for rec in parse_fixup_page(exe, le, zp):
                for s in rec['source_offsets']:
                    by_src[s].append(rec)
            page_cache[zp] = by_src
        matches = page_cache[zp].get(src_off, [])
        raw_file = object_raw_file_offset(exe, le, dispatch_obj, slot_off)
        raw_entry = exe[raw_file:raw_file+4]
        row = {
            'handler_id': hid,
            'dispatch_object': DISPATCH_OBJECT,
            'dispatch_object_offset': hex(slot_off),
            'dispatch_runtime_address': hex(dispatch_obj.base + slot_off),
            'dispatch_le_page': zp + 1,
            'dispatch_page_offset': hex(src_off),
            'raw_file_offset': hex(raw_file),
            'raw_entry': raw_entry.hex(),
            'matching_fixup_count': len(matches),
        }
        if len(matches) != 1:
            row['resolution'] = 'AMBIGUOUS' if matches else 'MISSING_FIXUP'
            errors.append((hid, row['resolution']))
        else:
            r = matches[0]
            row['fixup'] = r
            valid = ((r['source_type'] & 0x0F) == OFF32 and
                     r['target_kind'] == TARGET_INTERNAL and
                     (r['flags'] & TFLAG_OFF32) and
                     r['target_offset'] is not None and
                     1 <= r['target_object'] <= len(objects))
            if not valid:
                row['resolution'] = 'UNSUPPORTED_FIXUP'
                errors.append((hid, row['resolution']))
            else:
                tobj = objects[r['target_object']-1]
                if r['target_offset'] >= tobj.size:
                    row['resolution'] = 'TARGET_OUT_OF_RANGE'
                    errors.append((hid, row['resolution']))
                else:
                    row['target_object'] = r['target_object']
                    row['target_object_offset'] = hex(r['target_offset'])
                    row['resolved_runtime_target'] = hex(tobj.base + r['target_offset'])
                    row['target_raw_file_offset'] = hex(object_raw_file_offset(exe, le, tobj, r['target_offset']))
                    row['resolution'] = 'RESOLVED_INTERNAL_OFF32'
        entries[str(hid)] = row
    resolved = [e for e in entries.values() if e['resolution'] == 'RESOLVED_INTERNAL_OFF32']
    targets = [e['resolved_runtime_target'] for e in resolved]
    return {
        'exe': {'path': str(exe_path), 'size': len(exe), 'sha256': hashlib.sha256(exe).hexdigest(), 'format': 'LE'},
        'le': {
            'page_size': le['page_size'], 'page_count': le['num_pages'],
            'objects': [o.__dict__ for o in objects],
        },
        'dispatch': {
            'object': DISPATCH_OBJECT,
            'object_offset': hex(DISPATCH_OBJECT_OFFSET),
            'runtime_base': hex(dispatch_obj.base + DISPATCH_OBJECT_OFFSET),
        },
        'saves': by_save,
        'relevant_handler_count': len(all_ids),
        'resolved_handler_count': len(resolved),
        'unique_resolved_target_count': len(set(targets)),
        'resolution_errors': errors,
        'entries': entries,
        'dispatch_resolution': 'PASS' if not errors else 'PARTIAL',
        'movement_action_classification': 'NOT_YET_COMPLETE',
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True, type=Path)
    ap.add_argument('--save', action='append', required=True, type=Path)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args(); out = build(a.exe, a.save)
    if a.json: print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print(f"handlers={out['relevant_handler_count']} resolved={out['resolved_handler_count']} "
              f"unique_targets={out['unique_resolved_target_count']} status={out['dispatch_resolution']}")

if __name__ == '__main__':
    main()
