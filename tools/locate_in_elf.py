"""Find the functions the patch needs in the shipped main.dol by matching the
(relocation-masked) instructions of the same functions in the debug ELF."""
import struct, subprocess, sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from dol import Dol
from anchors import mask
NM = '/opt/devkitpro/devkitPPC/bin/powerpc-eabi-nm'
elf = open(os.path.join(HERE, '..', 'ref', 'SSR_Wii.elf'), 'rb').read()
TEXT_ADDR, TEXT_OFF = 0x80007fe0, 0x41c0
syms = {}
for l in subprocess.check_output([NM, '-n', os.path.join(HERE, '..', 'ref', 'SSR_Wii.elf')], text=True).splitlines():
    p = l.split(None, 2)
    if len(p) == 3: syms.setdefault(p[2], int(p[0], 16))
def ew(va, n):
    o = TEXT_OFF + va - TEXT_ADDR
    return list(struct.unpack('>%dI' % n, elf[o:o + 4 * n]))
dol = Dol(os.path.join(HERE, '..', 'dols', 'R3RE8P.dol'))
def tw():
    out = []
    for o, a, s, i in dol.secs:
        if i < 7:
            out.append((a, [mask(w) for w in struct.unpack('>%dI' % (s // 4), dol.data[o:o + s])]))
    return out
T = tw()
def find(va, n):
    m = [mask(w) for w in ew(va, n)]
    hits = []
    for a, t in T:
        for i in range(len(t) - n):
            if t[i] == m[0] and t[i:i + n] == m: hits.append(a + 4 * i)
    return hits
if __name__ == '__main__':
    for name in sys.argv[1:]:
        va = syms[name]
        print(name, hex(va), [hex(h) for h in find(va, int(os.environ.get('N', 24)))])
