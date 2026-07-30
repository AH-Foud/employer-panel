# -*- coding: utf-8 -*-
# Bale Bot + Web Management Panel
# Run: python run.py

import os, sys, time

os.makedirs("data", exist_ok=True)

# ── ANSI ──
RST  = '\033[0m'
HIDE = '\033[?25l'
SHOW = '\033[?25h'
CLR  = '\033[2J\033[H'

# ── Rainbow palette ──
RAINBOW = [
    '\033[38;2;91;154;255m',
    '\033[38;2;99;140;248m',
    '\033[38;2;129;140;248m',
    '\033[38;2;148;130;250m',
    '\033[38;2;167;139;250m',
    '\033[38;2;148;130;250m',
    '\033[38;2;129;140;248m',
    '\033[38;2;99;140;248m',
]
D = '\033[38;2;148;163;184m'
G = '\033[38;2;14;203;129m'
W = '\033[38;2;255;255;255m'
B = '\033[38;2;91;154;255m'

# ── Wave chars & colors (blue→purple gradient blocks) ──
WAVE_BLOCK = [
    ('█', '\033[38;2;91;154;255m'),   # blue
    ('▓', '\033[38;2;14;203;185m'),    # cyan-teal
    ('▒', '\033[38;2;129;140;248m'),   # indigo
    ('░', '\033[38;2;167;139;250m'),   # purple
    ('▒', '\033[38;2;200;120;240m'),   # magenta
    ('▓', '\033[38;2;14;203;185m'),    # cyan-teal
]
BLOCK_LEN = len(WAVE_BLOCK)

# ── BALE logo ──
BALE = [
    '  ██████╗  █████╗ ██╗     ███████╗',
    '  ██╔══██╗██╔══██╗██║     ██╔════╝',
    '  ██████╔╝███████║██║     █████╗  ',
    '  ██╔══██╗██╔══██║██║     ██╔══╝  ',
    '  ██████╔╝██║  ██║███████╗███████╗',
    '  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝',
]

# ═══════════════════════════════════════════════
#  EFFECTS
# ═══════════════════════════════════════════════

def wave_row(width, offset):
    """Build a single wave row with shifted block pattern"""
    row = ''
    for x in range(width):
        idx = (x + offset) % BLOCK_LEN
        ch, color = WAVE_BLOCK[idx]
        row += color + ch + RST
    return row


def wave_animation(rows=18, cols=52, frames=12, speed=0.06):
    """
    Animated background wave — shifting █▓▒░ blocks
    Returns after animation completes, screen is left with final wave frame.
    """
    for frame in range(frames):
        sys.stdout.write('\033[H')  # jump to top
        offset = frame  # shift wave each frame
        for y in range(rows):
            # each row has its own phase shift for a multi-layered wave
            row_offset = offset + y * 2
            line = '  ' + wave_row(cols, row_offset)
            # add padding to clear the line fully
            sys.stdout.write(line + '\033[K\n')
        sys.stdout.flush()
        time.sleep(speed)


def typeprint_rainbow(text, delay=0.006):
    i = 0
    while i < len(text):
        if text[i] == '\033':
            j = text.index('m', i) + 1 if 'm' in text[i:] else i + 1
            sys.stdout.write(text[i:j])
            i = j
            continue
        c = RAINBOW[i % len(RAINBOW)]
        sys.stdout.write(c + text[i] + RST)
        sys.stdout.flush()
        if text[i] not in ' \n\r\t═╔╗║╚╝╭╮╰╯─│█▌▐▀▄■□▪▫':
            time.sleep(delay)
        i += 1


def typeprint_fade(text, delay=0.003):
    L = max(len(text.strip()) or 1, 1)
    i = 0
    while i < len(text):
        if text[i] == '\033':
            j = text.index('m', i) + 1 if 'm' in text[i:] else i + 1
            sys.stdout.write(text[i:j])
            i = j
            continue
        ratio = i / L
        r = int(91 + (167 - 91) * ratio)
        g = int(154 - (154 - 139) * ratio)
        bv = int(255 - (255 - 250) * ratio)
        sys.stdout.write(f'\033[38;2;{r};{g};{bv}m{text[i]}\033[0m')
        sys.stdout.flush()
        if text[i] not in ' \n\r\t═╔╗║╚╝╭╮╰╯─│█▌▐▀▄■□▪▫':
            time.sleep(delay)
        i += 1


def typeprint(text, delay=0.015):
    i = 0
    while i < len(text):
        if text[i] == '\033':
            j = text.index('m', i) + 1 if 'm' in text[i:] else i + 1
            sys.stdout.write(text[i:j])
            i = j
            continue
        sys.stdout.write(text[i])
        sys.stdout.flush()
        if text[i] not in ' \n\r\t═╔╗║╚╝╭╮╰╯─│█▌▐▀▄■□▪▫':
            time.sleep(delay)
        i += 1


def loading_pulse(msg, cycles=3, speed=0.12):
    for _ in range(cycles):
        for pos in range(3):
            dots = ''
            for d in range(3):
                dots += f'{G}●{RST}' if d == pos else f'{D}·{RST}'
            sys.stdout.write(f'\r  {B}⬢{RST}  {msg}  {dots}  ')
            sys.stdout.flush()
            time.sleep(speed)
    sys.stdout.write(f'\r  {G}⬢{RST}  {msg}  {G}done{RST}\n')


# ═══════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════

if __name__ == "__main__":
    sys.stdout.write(HIDE)
    sys.stdout.write(CLR)

    # ── WAVE BACKGROUND — 2 sec animated ──
    wave_animation(rows=18, cols=52, frames=12, speed=0.06)

    # ── Clear + BALE logo overlay ──
    sys.stdout.write(CLR)
    sys.stdout.write('\n')

    # top border
    typeprint_fade(f'  ╔{"═" * 44}╗', 0.002)
    sys.stdout.write('\n')

    # BALE — rainbow typing
    for line in BALE:
        sys.stdout.write(f'{B}  ║{RST}')
        typeprint_rainbow(line, delay=0.003)
        sys.stdout.write(f'{B}  ║{RST}\n')
        time.sleep(0.025)

    # color wave — 2 re-color passes
    for wave in range(2):
        sys.stdout.write('\033[6A')
        for li, line in enumerate(BALE):
            offset = wave * 3 + li
            sys.stdout.write(f'{B}  ║{RST}')
            for i, ch in enumerate(line):
                c = RAINBOW[(i + offset) % len(RAINBOW)]
                sys.stdout.write(c + ch + RST)
            sys.stdout.write(f'{B}  ║{RST}\n')
        sys.stdout.flush()
        time.sleep(0.15)

    # final fast rainbow reprint
    sys.stdout.write('\033[6A')
    for line in BALE:
        sys.stdout.write(f'{B}  ║{RST}')
        typeprint_rainbow(line, delay=0.001)
        sys.stdout.write(f'{B}  ║{RST}\n')

    # version
    sys.stdout.write(f'{B}  ║{RST}{D}         Bot + Dashboard {G}v5.2              {B}║{RST}\n')

    # bottom border
    typeprint_fade(f'  ╚{"═" * 44}╝', 0.002)
    sys.stdout.write('\n\n')

    # init
    typeprint(f'  {B}⬢{RST}  {W}Launching Bale Bot{RST}\n\n', 0.012)
    loading_pulse('Bot Engine', 3, 0.12)
    loading_pulse('Dashboard', 3, 0.1)
    loading_pulse('SOP Matcher', 3, 0.1)

    sys.stdout.write('\n')
    sys.stdout.write(f'  {G}●{RST}  {D}Ready — dashboard is live{RST}\n')
    sys.stdout.write(f'{D}  {"─" * 44}{RST}\n\n')
    sys.stdout.write(SHOW)

    from web_server import run
    run()
