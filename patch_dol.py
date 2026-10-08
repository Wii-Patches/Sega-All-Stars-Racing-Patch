#!/usr/bin/env python3
"""Add GameCube-controller support to a Sonic & SEGA All-Stars Racing (Wii) main.dol.

  patch_dol.py <in main.dol> <out main.dol>

The disc is identified by resolving the hook sites against it (anchors.py); build.py compiles
the three hook bodies for it.  The bodies and their state go in a new DOL text section in low memory
(0x80001820 -- not 0x80001800, which a loader's code handler overwrites -- and below the OS globals
at 0x80003000).  Each hook site becomes a branch into its body, and the last word of every body
branches back to site+4, which is what a Gecko C2 code does.
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
sys.path.insert(0, HERE)
import build

BASE = 0x80001820
LIMIT = 0x80003000


def branch(frm, to):
    off = to - frm
    assert off % 4 == 0 and -0x2000000 <= off < 0x2000000
    return 0x48000000 | (off & 0x03FFFFFC)


class Dol:
    def __init__(self, data):
        self.d = bytearray(data)
        self.off = list(struct.unpack('>18I', self.d[0x00:0x48]))
        self.addr = list(struct.unpack('>18I', self.d[0x48:0x90]))
        self.size = list(struct.unpack('>18I', self.d[0x90:0xD8]))

    def v2f(self, va):
        for o, a, s in zip(self.off, self.addr, self.size):
            if s and a <= va < a + s:
                return o + va - a
        raise KeyError(hex(va))

    def word(self, va):
        return struct.unpack('>I', self.d[self.v2f(va):][:4])[0]

    def put(self, va, word):
        self.d[self.v2f(va):self.v2f(va) + 4] = struct.pack('>I', word)

    def add_text(self, va, blob):
        slot = next((i for i in range(7) if self.size[i] == 0), None)
        if slot is None:
            raise RuntimeError('no free text section in the DOL header')
        for a, s in zip(self.addr, self.size):
            if s and a < va + len(blob) and va < a + s:
                raise RuntimeError('0x%08X overlaps an existing section' % va)
        while len(self.d) % 0x20:
            self.d.append(0)
        self.off[slot], self.addr[slot], self.size[slot] = len(self.d), va, len(blob)
        self.d += blob
        self.d[0x00:0x48] = struct.pack('>18I', *self.off)
        self.d[0x48:0x90] = struct.pack('>18I', *self.addr)
        self.d[0x90:0xD8] = struct.pack('>18I', *self.size)


def apply(data, patch):
    """patch: {'sites': [[site, [words]]], 'state': va, 'orig': {site: word}}"""
    dol = Dol(data)
    state = patch['state']
    sites = patch['sites']
    blob = bytearray()
    placed = []
    for site, words in sites:
        at = BASE + len(blob)
        w = list(words)
        w[-1] = branch(at + 4 * (len(w) - 1), site + 4)
        blob += struct.pack('>%dI' % len(w), *w)
        placed.append((site, at))
    if BASE + len(blob) > state:
        raise RuntimeError('hook code (%d bytes) runs into the state area' % len(blob))
    blob += bytes(state + 0x80 - BASE - len(blob))      # zeroed state
    if BASE + len(blob) > LIMIT:
        raise RuntimeError('patch does not fit in low memory below 0x%08X' % LIMIT)
    for site, orig in patch['orig'].items():
        if dol.word(int(site)) != orig:
            raise RuntimeError('hook site 0x%08X does not hold the expected instruction (already patched?)' % int(site))
    dol.add_text(BASE, bytes(blob))
    for site, at in placed:
        dol.put(site, branch(site, at))
    return bytes(dol.d)


if __name__ == '__main__':
    src, dst = sys.argv[1:3]
    data = open(src, 'rb').read()
    patch = build.for_dol(src)
    out = apply(data, patch)
    open(dst, 'wb').write(out)
    print('patched (%d bytes added)' % (len(out) - len(data)))
