#!/usr/bin/env python3
"""Compile the GameCube-pad hooks for a game revision and emit the patch (DOL patch + Gecko code).

  build.py [--gecko OUT.txt]  [main.dol ...]       (default: every dols/*.dol)

Needs devkitPPC.  USA (R3RE8P) is the reference; anchors.py relocates to other revisions.
"""
import glob, os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'tools'))
sys.path.insert(0, HERE)
from dol import Dol
import anchors

DEVKIT = os.environ.get('DEVKITPPC', '/opt/devkitpro/devkitPPC')
CC = DEVKIT + '/bin/powerpc-eabi-'
STATE = 0x80002800          # zeroed by the patch section itself (patch_dol.py)
REF = os.path.join(HERE, 'dols', 'R3RE8P.dol')


def compile_hook(name, defs):
    src = os.path.join(HERE, 'src')
    tmp = tempfile.mkdtemp(prefix='gcpad')
    D = ['-D%s=%s' % kv for kv in defs.items()] + ['-DHOOK_' + name]
    if os.environ.get('DEBUG_FEED'):
        D.append('-DDEBUG_FEED')
    cflags = ['-O2', '-fno-unroll-loops', '-mbig-endian', '-msoft-float', '-msdata=none', '-ffreestanding', '-fno-pic',
              '-fno-asynchronous-unwind-tables', '-fno-stack-protector', '-nostdlib', '-Wall']
    subprocess.check_call([CC + 'gcc'] + cflags + D + ['-c', src + '/gcpad.c', '-o', tmp + '/g.o'])
    subprocess.check_call([CC + 'gcc', '-mbig-endian', '-c', '-x', 'assembler-with-cpp'] + D +
                          [src + '/hooks.S', '-o', tmp + '/h.o'])
    subprocess.check_call([CC + 'ld', '-T', src + '/link.ld', '-o', tmp + '/b.elf', tmp + '/h.o', tmp + '/g.o'])
    subprocess.check_call([CC + 'objcopy', '-O', 'binary', tmp + '/b.elf', tmp + '/b.bin'])
    b = open(tmp + '/b.bin', 'rb').read()
    return list(struct.unpack('>%dI' % (len(b) // 4), b))


def for_dol(path):
    dol = Dol(path)
    a = anchors.resolve(Dol(REF), dol)
    defs = {
        'STATE': '0x%08Xu' % STATE,
        'SI_TYPES': '0x%08Xu' % a['SiTypes'],
        'SI_BUSY': '0x%08Xu' % a['SiBusy'],
        'SI_SHADOW': '0x%08Xu' % a['SiShadow'],
        'FN_SIGETTYPE': '0x%08Xu' % a['SIGetType'],
        'FN_OSDISABLE': '0x%08Xu' % a['OSDisableInterrupts'],
        'FN_OSRESTORE': '0x%08Xu' % a['OSRestoreInterrupts'],
        'WPAD_TBL': '0x%08Xu' % a['WpadTbl'],
    }
    hooks = [('READ', a['WPADReadCopy']), ('PROBE', a['WPADProbe'])]
    sites, orig = [], {}
    for name, site in hooks:
        w = compile_hook(name, defs)
        assert w[-1] == 0x60000000          # the slot patch_dol turns into the branch back
        if len(w) % 2:
            w.insert(len(w) - 1, 0x60000000)
        sites.append([site, w])
        orig[str(site)] = struct.unpack('>I', dol.read(site, 4))[0]
    return {'state': STATE, 'sites': sites, 'orig': orig, 'anchors': a}


def gecko_text(title, patch):
    lines = [title]
    for site, data in patch['sites']:
        data = list(data)
        data[-1] = 0                        # C2 appends the branch back itself
        lines.append('C2%06X %08X' % (site & 0x01FFFFFF, len(data) // 2))
        for i in range(0, len(data), 2):
            lines.append('%08X %08X' % (data[i], data[i + 1]))
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    args = sys.argv[1:]
    gecko = None
    if '--gecko' in args:
        i = args.index('--gecko'); gecko = args[i + 1]; del args[i:i + 2]
    for p in args or sorted(glob.glob(os.path.join(HERE, 'dols', '*.dol'))):
        patch = for_dol(p)
        print(os.path.basename(p), {k: '%08X' % v for k, v in patch['anchors'].items()}, [len(w) * 4 for _, w in patch['sites']])
        if gecko:
            open(gecko, 'w').write(gecko_text('Classic Controller + GameCube Controller (port 1)', patch))
