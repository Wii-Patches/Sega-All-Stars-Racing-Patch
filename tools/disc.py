"""Patch a whole Sonic & SEGA All-Stars Racing disc image: extract with wit, patch sys/main.dol, rebuild.

The rebuilt image replaces the original in place (USB loaders key off the
`/wbfs/<Title> [ID6]/` layout); the untouched original is kept as `<name>.bak`.
An .rvz/.wia/.gcz input is written next to it as a .wbfs instead.
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patcher
from regions import REGIONS

DISC_EXT = ('.wbfs', '.iso', '.rvz', '.wia', '.gcz', '.ciso')


def find_wit():
    name = 'wit.exe' if os.name == 'nt' else 'wit'
    if getattr(sys, 'frozen', False):
        for base in (getattr(sys, '_MEIPASS', None), os.path.dirname(sys.executable)):
            if base and os.path.isfile(os.path.join(base, name)):
                return os.path.join(base, name)
    return shutil.which('wit')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError((r.stderr or r.stdout).strip())


def run_patch(image, log, done):
    try:
        wit = find_wit()
        if not wit:
            raise RuntimeError('wit (Wiimms ISO Tool) not found: not bundled with this build and not on PATH')
        ext = os.path.splitext(image)[1].lower()
        in_place = ext in ('.wbfs', '.iso')
        dest = image if in_place else os.path.splitext(image)[0] + '.wbfs'
        with tempfile.TemporaryDirectory(prefix='ssasr_patch_') as tmp:
            fst = os.path.join(tmp, 'fst')
            log('extracting %s...' % os.path.basename(image))
            run([wit, 'extract', image, '--dest', fst, '--psel', 'data', '--overwrite', '-q'])
            with open(os.path.join(fst, 'sys', 'boot.bin'), 'rb') as f:
                gid = f.read(6).decode('ascii', 'replace')
            if gid not in REGIONS:
                raise RuntimeError('%s is not a supported disc. Supported:\n%s' % (
                    gid, '\n'.join('  %s: %s' % kv for kv in REGIONS.items())))
            log('disc: %s (%s)' % (gid, REGIONS[gid]))
            dol = os.path.join(fst, 'sys', 'main.dol')
            out = patcher.patch_bytes(open(dol, 'rb').read())
            if out is None:
                log('this disc is already patched; nothing to do.')
                done(True, 'Already patched')
                return
            open(dol, 'wb').write(out)
            log('patched main.dol')
            if in_place and not os.path.exists(image + '.bak'):
                log('keeping the original as %s.bak...' % os.path.basename(image))
                shutil.copy2(image, image + '.bak')
            log('rebuilding %s...' % os.path.basename(dest))
            run([wit, 'copy', fst, dest, '--iso' if dest.lower().endswith('.iso') else '--wbfs', '--overwrite', '-q'])
        log('done!')
        done(True, dest)
    except Exception as e:
        log('Error: %s' % e)
        done(False, str(e))


if __name__ == '__main__':
    run_patch(sys.argv[1], print, lambda ok, msg: sys.exit(0 if ok else msg))
