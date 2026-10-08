"""Find the addresses the GameCube-pad patch needs in any revision of the game.

Everything is written once against the USA disc (R3RE8P); other regions share the same compiled
code at other addresses.  A function is located by matching a window of USA instructions against
the target DOL with the relocatable bits (branch displacements, address halves, small-data
offsets) masked out, and it must match exactly once.  Data addresses are then read back from the
matched code (the lis/addi that references them), never guessed.
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tools'))
from dol import Dol


def mask(w):
    op = w >> 26
    if op == 18:                         # b / bl: keep opcode, AA, LK
        return w & 0xFC000003
    if op == 16:                         # bc: keep everything but displacement
        return w & 0xFFFF0003
    if op in (14, 15, 24, 25, 26, 27, 28, 29):   # addi/lis/ori/oris/xori/andi
        return w & 0xFFFF0000
    if 32 <= op <= 55:                   # loads/stores: drop displacement
        return w & 0xFFFF0000
    return w


def words(d, va, n):
    b = d.read(va, n * 4)
    return list(struct.unpack('>%dI' % n, b)) if b and len(b) == n * 4 else None


class Finder:
    def __init__(self, ref, tgt):
        self.ref, self.tgt = ref, tgt
        self.text = []
        for o, a, s, i in tgt.secs:
            if i < 7:
                self.text.append((a, [mask(w) for w in struct.unpack('>%dI' % (s // 4), tgt.data[o:o + s])]))

    def locate(self, ref_va, n=24):
        """address in the target of the code at ref_va; must match exactly once"""
        rm = [mask(w) for w in words(self.ref, ref_va, n)]
        hits = []
        for base, tm in self.text:
            for i in range(len(tm) - n):
                if tm[i] == rm[0] and tm[i:i + n] == rm:
                    hits.append(base + 4 * i)
        if len(hits) != 1:
            raise SystemExit('anchor %08X: %d matches' % (ref_va, len(hits)))
        return hits[0]

    def pair(self, ref_va, ref_target, n=64):
        """the target revision's value for the address that the lis + addi pair near ref_va
        loads (ref_target on the USA disc)"""
        t_va = self.locate(ref_va)
        rw = words(self.ref, ref_va, n)
        tw = words(self.tgt, t_va, n)

        def imm(w):
            v = w & 0xFFFF
            return v - 0x10000 if v & 0x8000 else v

        for i in range(n):
            w = rw[i]
            if w >> 26 != 15:
                continue
            reg = (w >> 21) & 31
            for j in range(i + 1, min(n, i + 16)):
                w2 = rw[j]
                if w2 >> 26 == 14 and (w2 >> 16) & 31 == reg:
                    val = ((w & 0xFFFF) << 16) + imm(w2)
                    if val & 0xFFFFFFFF == ref_target:
                        t, t2 = tw[i], tw[j]
                        assert t >> 26 == 15 and t2 >> 26 == 14
                        return (((t & 0xFFFF) << 16) + imm(t2)) & 0xFFFFFFFF
        raise SystemExit('no pair for %08X near %08X' % (ref_target, ref_va))


# (name, USA address, window)
FUNCS = {
    'WPADRead':            (0x804110C0, 40),
    'WPADProbe':           (0x80410730, 40),
    'SIGetType':           (0x80380500, 40),
    'OSDisableInterrupts': (0x80376F70, 6),
    'OSRestoreInterrupts': (0x80376FB0, 6),
}
# the `mr r3,r30` in WPADRead right after it copied the channel's status into the caller's buffer
READ_COPY_OFF = 0x80411180 - 0x804110C0


def resolve(ref, tgt):
    f = Finder(ref, tgt)
    r = {k: f.locate(v, n) for k, (v, n) in FUNCS.items()}
    r['WPADReadCopy'] = r['WPADRead'] + READ_COPY_OFF
    r['SiTypes'] = f.pair(0x80380500, 0x804CEFC8)      # SI type cache, Type[4]
    r['SiBusy'] = r['SiTypes'] - 0x18                  # Si.chan: -1 while idle
    r['SiShadow'] = r['SiBusy'] + 4                    # Si.poll: SIPOLL shadow
    r['WpadTbl'] = f.pair(0x80410730, 0x807199B0)      # per-channel WPAD block pointers
    return r


if __name__ == '__main__':
    ref = Dol(sys.argv[1])
    for p in sys.argv[2:]:
        r = resolve(ref, Dol(p))
        print(os.path.basename(p), {k: '%08X' % v for k, v in r.items()})
