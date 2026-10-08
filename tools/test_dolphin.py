#!/usr/bin/env python3
"""Boot the patched game in Dolphin with a scripted GameCube pad on port 1 (no Wii Remote) and read
KPAD channel 0 back over the GDB stub.

  test_dolphin.py <patched image> [boot seconds]        (env: VIDEO=Metal for a window)
"""
import os, struct, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dolphin_gc import prepare, launch, stop, Pad
from gdbmem import Gdb

KPAD0 = 0x8071D148          # KPAD channel 0 block (stride 0x578)

def kpad(g):
    b = g.read_mem(KPAD0, 0x180)
    return dict(dev=b[0x5C], err=b[0x5D], idx=b[0x13A], cnt=b[0x13B],
                s0=b[0x13C:0x13C + 0x38].hex())

def main():
    image = sys.argv[1]
    boot = float(sys.argv[2]) if len(sys.argv) > 2 else 60
    user = os.path.abspath(os.environ.get('USERDIR', os.path.join(HERE, '..', 'dolphin_user')))
    prepare(user, '-', 'R3RE8P')
    launch(user, image, os.environ.get('VIDEO', 'Null'))
    g = None
    for _ in range(120):
        try:
            g = Gdb(timeout=30); break
        except OSError:
            time.sleep(1)
    pad = Pad(user)
    g.cont()
    try:
        time.sleep(boot)
        for name in ['A', 'B', 'X', 'Y', 'Z', 'Start', 'L', 'R']:
            pad.press(name); time.sleep(0.8)
            g.interrupt(); k = kpad(g); print('%-6s' % name, k, flush=True); g.cont()
            pad.release(name); time.sleep(0.4)
        pad.stick('MAIN', 1.0, 0.5); time.sleep(0.8)
        g.interrupt(); print('stick', kpad(g)); g.cont()
    finally:
        stop(user)

if __name__ == '__main__':
    main()
