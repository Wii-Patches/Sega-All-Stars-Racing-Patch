# GameCube controller for Sonic & SEGA All-Stars Racing (Wii)

Plug a GameCube controller into **port 1**. The pad shows up to the game as a Classic Controller,
which the game already supports (`ControllerWii::ConvertPadData`, extension type 2), so the rest of
the game's controller code is untouched.

**Status: works in Dolphin** (USA, DOL patch and Gecko code), with no Wii Remote connected: title
screen, menus (D-pad, stick, A/B), name entry, Mii select and driving the test drive (gas, steering).
Pad input was fed through the patch's debug build; not yet tried with a real pad on a console.
Europe (R3RP8P) uses the same code addresses, so the same patch applies.

## How it works
The game polls controllers through `WPADProbe` and `WPADRead`, and never links the PAD library.
Two hooks (`src/gcpad.c`, `src/hooks.S`), approach from Barrel Blast Patch / ACCF gcpad:

| Hook | Site | What it does |
| --- | --- | --- |
| probe | `WPADProbe` entry | Drives the Serial Interface's auto-polling for port 1, then reports a Classic Controller on channel 0 while a pad is plugged in |
| read | `WPADRead`, after the status copy | Writes the pad into the game's status buffer as a Classic Controller sample; a real Nunchuk or Classic Controller is never overridden |

## Controls
GameCube A/B/X/Y/L/R/D-pad/sticks map to the same Classic Controller inputs, Z is ZR, Start is +.

## Building
Needs devkitPPC and your own `main.dol` at `dols/R3RE8P.dol` (USA) or `dols/R3RP8P.dol` (Europe), not included.

    python3 build.py --gecko gecko/R3RE8P.txt     # compile hooks, write the Gecko code
    python3 patch_dol.py dols/R3RE8P.dol main.dol # or patch a main.dol directly

`anchors.py` resolves addresses by matching code, so other regions can be added by dropping their
`main.dol` into `dols/`. The Gecko code keeps its state at 0x80002FC0 (top of the loader's code-list
window); the DOL patch keeps it at 0x80002800. Don't combine the Gecko code with the DOL patch; they are the same hooks.
