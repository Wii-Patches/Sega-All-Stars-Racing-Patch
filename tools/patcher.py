#!/usr/bin/env python3
"""Add GameCube-controller support to a Sonic & SEGA All-Stars Racing main.dol from the prebuilt patch.

  patcher.py <in main.dol> <out main.dol>
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..'))
import patch_dol
from regions import DOL_MD5, PREBUILT


def prebuilt_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(getattr(sys, '_MEIPASS', os.path.dirname(sys.executable)), 'prebuilt')
    return os.path.join(HERE, 'prebuilt')


def load():
    with open(os.path.join(prebuilt_dir(), PREBUILT)) as f:
        return json.load(f)


def status(data):
    """'clean' (retail), 'patched' (this patch already applied) or 'unknown'"""
    if hashlib.md5(data).hexdigest() == DOL_MD5:
        return 'clean'
    p = load()
    d = patch_dol.Dol(data)
    try:
        if all(d.word(int(s)) >> 26 == 18 and d.word(int(s)) != o for s, o in p['orig'].items()) \
                and any(a == patch_dol.BASE for a in d.addr):
            return 'patched'
    except KeyError:
        pass
    return 'unknown'


def patch_bytes(data):
    st = status(data)
    if st == 'patched':
        return None
    if st != 'clean':
        raise RuntimeError('main.dol is not an unmodified Sonic & SEGA All-Stars Racing (USA/Europe) main.dol')
    return patch_dol.apply(data, load())


if __name__ == '__main__':
    src, dst = sys.argv[1:3]
    out = patch_bytes(open(src, 'rb').read())
    if out is None:
        sys.exit('already patched')
    open(dst, 'wb').write(out)
    print('patched')
