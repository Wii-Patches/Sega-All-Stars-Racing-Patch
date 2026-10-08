import sys, os, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dol import Dol
cs = importlib.import_module('capstone')
md = cs.Cs(cs.CS_ARCH_PPC, cs.CS_MODE_32 | cs.CS_MODE_BIG_ENDIAN)
if __name__ == '__main__':
    a = int(sys.argv[1], 16); n = int(sys.argv[2], 0)
    d = Dol(os.environ.get('DOL', 'dols/R3RE8P.dol'))
    for i in md.disasm(d.read(a, n), a):
        print('%x: %s %s' % (i.address, i.mnemonic, i.op_str))
