/* GameCube controller (port 1) -> Classic Controller bridge for Sonic & SEGA All-Stars Racing (Wii).
 *
 * The game already has a complete Classic Controller path (ControllerWii::ConvertPadData, extension
 * type 2).  What it lacks is anything that talks to a GameCube pad: the build links the SI library
 * but not PAD, so nothing ever polls the pads, and with no Wii Remote there is no KPAD sample for
 * the Classic Controller code to read.  The game polls its controllers through WPADProbe and WPADRead
 * (not KPAD), so two hooks, one blob each (see hooks.S for the register-saving entry stubs):
 *
 *   probe  - WPADProbe entry: first drives the Serial Interface's own auto-polling for port 1 (it is
 *            called every frame), then reports a Classic Controller on channel 0 while a pad is
 *            plugged in, so the game believes one is connected
 *   read   - WPADRead, after it copied the channel's status out: writes the pad into the game's
 *            status buffer as a Classic Controller sample, so the game sees an ordinary one
 *
 * Addresses come in as -D macros, resolved by anchors.py.
 */
typedef unsigned int u32;
typedef signed int s32;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned char u8;
typedef signed char s8;

#define R32(a) (*(volatile u32 *)(a))
#define SI_OUT0   (0xCD006400u)
#define SI_IN0H   (0xCD006404u)
#define SI_IN0L   (0xCD006408u)
#define SI_POLL   (0xCD006430u)
#define SI_COMCSR (0xCD006434u)
#define SI_SR     (0xCD006438u)

struct st {
    u32 probe_tb;   /* last SIGetType */
    u32 busy_tb;    /* when si:: was first seen busy (0 = idle) */
    u8 norep;       /* consecutive frames with NOREP on port 1 */
};
#define ST ((volatile struct st *)STATE)

static inline u32 tb(void)
{
    u32 t;
    __asm__ volatile("mftb %0" : "=r"(t));
    return t;
}

/* a valid, error-free pad response on port 1 */
static inline int gc_in(u32 *h, u32 *l)
{
#ifdef DEBUG_FEED
    /* test builds: the pad's response is written to STATE+0x20/0x24 by a debugger */
    if (!R32(STATE + 0x20))
        return 0;
    *h = R32(STATE + 0x20);
    *l = R32(STATE + 0x24);
    return 1;
#endif
    u32 v = R32(SI_IN0H);
    if ((v & 0x80000000u) || !(v & 0x00800000u))
        return 0;
    *h = v;
    *l = R32(SI_IN0L);
    return 1;
}

#if defined(HOOK_PROBE)
static void gc_poll(u32 chan)
{
    volatile u32 *types = (volatile u32 *)SI_TYPES;
    u32 type, sisr, mask, poll;
    int confirmed;
    s32 busy;

    if (chan)
        return;

    /* probe the port until a standard pad answers, at most every 0.25 s:
     * probing every frame collides with the pad's own polling on hardware */
    type = types[0];
    confirmed = !(type & 0x80) && (type & 0x18000000u) == 0x08000000u;
    if (!confirmed) {
        u32 now = tb();
        if (now - ST->probe_tb >= 15187500u) {
            ST->probe_tb = now;
            ((u32 (*)(u32))FN_SIGETTYPE)(0);
        }
    }

    /* an unplugged pad latches NOREP; si:: never reads it (no PAD library),
     * so copy a persistent one into the type cache ourselves, which makes
     * SIGetType probe the port again once a pad is plugged back in */
    sisr = R32(SI_SR);
    if (sisr & 0x08000000u) {
        if (ST->norep < 10)
            ST->norep++;
        else
            types[0] = 8;
    } else {
        ST->norep = 0;
    }

    R32(SI_OUT0) = 0x00400300u;                    /* poll command */
    R32(SI_SR) = (sisr & 0x0F0F0F0Fu) | 0x80000000u; /* ack errors, latch OUT */

    type = types[0];
    confirmed = !(type & 0x80) && (type & 0x18000000u) == 0x08000000u;
    mask = confirmed ? 0x88u : 0;                  /* EN0 + VBCPY0 */
    poll = R32(SI_POLL) & ~0xFFu;
    if (!(poll & 0xFF00u))
        poll |= 0x0100u;
    R32(SI_POLL) = poll | mask;
    /* si:: rewrites SIPOLL from its own shadow on every retrace */
    R32(SI_SHADOW) = (R32(SI_SHADOW) & ~0xFFu) | mask;

    /* a pad unplugged mid-transfer leaves si::'s global busy flag wedged
     * (nothing times it out); force it idle after a second */
    busy = (s32)R32(SI_BUSY);
    if (busy == -1) {
        ST->busy_tb = 0;
    } else {
        u32 now = tb();
        if (ST->busy_tb == 0) {
            ST->busy_tb = now | 1;
        } else if (now - ST->busy_tb >= 60750000u) {
            u32 lvl = ((u32 (*)(void))FN_OSDISABLE)();
            R32(SI_BUSY) = (u32)-1;
            R32(SI_COMCSR) = 0x80000000u;
            ((void (*)(u32))FN_OSRESTORE)(lvl);
            ST->busy_tb = 0;
        }
    }
}
#endif

#if defined(HOOK_READ)
/* Classic Controller buttons as WPAD reports them */
#define CL_UP    0x0001
#define CL_LEFT  0x0002
#define CL_ZR    0x0004
#define CL_X     0x0008
#define CL_A     0x0010
#define CL_Y     0x0020
#define CL_B     0x0040
#define CL_ZL    0x0080
#define CL_R     0x0200
#define CL_PLUS  0x0400
#define CL_MINUS 0x1000
#define CL_L     0x2000
#define CL_DOWN  0x4000
#define CL_RIGHT 0x8000

static inline s16 stick(u32 raw)
{
    /* GameCube sticks are unsigned bytes centred on 128 and reach about +-100; the Classic Controller
     * values the game normalises (ConvertPadData) saturate at about +-322 */
    s32 v = ((s32)(raw & 0xFF) - 128) * 3;
    if (v > 330)
        v = 330;
    if (v < -330)
        v = -330;
    return (s16)v;
}

static __attribute__((noinline)) u32 cc_buttons(u32 h)
{
    u32 b = 0;

    if (h & 0x01000000u) b |= CL_A;
    if (h & 0x02000000u) b |= CL_B;
    if (h & 0x04000000u) b |= CL_X;
    if (h & 0x08000000u) b |= CL_Y;
    if (h & 0x10000000u) b |= CL_PLUS;       /* Start */
    if (h & 0x00100000u) b |= CL_ZR;         /* Z */
    if (h & 0x00400000u) b |= CL_L;
    if (h & 0x00200000u) b |= CL_R;
    if (h & 0x00080000u) b |= CL_UP;
    if (h & 0x00040000u) b |= CL_DOWN;
    if (h & 0x00020000u) b |= CL_RIGHT;
    if (h & 0x00010000u) b |= CL_LEFT;
    return b;
}

static __attribute__((noinline)) void fill_cc(u8 *s, u32 h, u32 l, u32 b)
{
    *(u16 *)(s + 0x2A) = (u16)b;
    *(s16 *)(s + 0x2C) = stick(h >> 8);      /* control stick x */
    *(s16 *)(s + 0x2E) = stick(h);           /* control stick y */
    *(s16 *)(s + 0x30) = stick(l >> 24);     /* C-stick x */
    *(s16 *)(s + 0x32) = stick(l >> 16);     /* C-stick y */
    s[0x34] = (h & 0x00400000u) ? 180 : 0;   /* digital L / R */
    s[0x35] = (h & 0x00200000u) ? 180 : 0;
    s[0x28] = 2;                             /* extension: Classic Controller */
    s[0x29] = 0;                             /* no extension error */
    s[0x36] = 8;                             /* classic + accel + pointer data */
}

/* WPADRead(chan, buf), after the copy: `buf` is the game's status buffer, `blk` the channel's WPAD block.
 * A real Nunchuk or Classic Controller is never touched; a bare Wii Remote (or no remote at all) gets the
 * pad as a Classic Controller. */
void gc_read(u8 *buf, u8 *blk)
{
    u32 h, l;

    if (blk != *(u8 **)WPAD_TBL || !gc_in(&h, &l))
        return;
    if (buf[0x29] == 0 && (buf[0x28] == 1 || buf[0x28] == 2))
        return;
    fill_cc(buf, h, l, cc_buttons(h));
}
#endif

#if defined(HOOK_PROBE)
/* WPADProbe(chan, &type): report a Classic Controller on channel 0 while a
 * pad is plugged in, unless the channel already has a real extension */
u32 gc_probe(u32 chan, u32 *type)
{
    u32 h, l;
    u8 *blk;
    u32 t;
    s32 status;

    gc_poll(chan);
    if (chan || !gc_in(&h, &l))
        return 0;
    blk = *(u8 **)(WPAD_TBL + chan * 4);
    t = blk[2241];
    status = *(s32 *)(blk + 2236);
    if (status != -1 && (t == 1 || t == 2))
        return 0;
    if (type)
        *type = 2;
    return 1;
}
#endif
