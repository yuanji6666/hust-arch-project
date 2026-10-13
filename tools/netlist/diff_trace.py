#!/usr/bin/env python3
"""
Single-step comparison: simulate the same program in Python (a reference model
of the 24-line ISA subset) and run it through the circuit trace, then report the
FIRST architectural divergence with full context.

Because the Logisim table trace reports RDin (the value the register file is
being asked to write) and PC/IR per clock, we can rebuild the architectural
state cycle by cycle and compare against the ISA model.

Usage: diff_trace.py <traceFile> <romHexFile>
"""
import re
import sys

HEADER_RE = re.compile(
    r"^\s*([01E])\s+([01E])\s+([0-9a-f]{8})\s+([0-9a-f]{8})"
    r"\s+([0-9a-f]{8})\s+([0-9a-f]{8})\s+([0-9a-f]{8})")

MASK = 0xFFFFFFFF


def parse(path):
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = HEADER_RE.match(line)
        if m:
            rows.append(dict(rw=m.group(1), mw=m.group(2), pc=int(m.group(3), 16),
                             ir=int(m.group(4), 16), rdin=int(m.group(5), 16),
                             mdin=int(m.group(6), 16), led=int(m.group(7), 16)))
    return rows


def load_rom(path):
    words = []
    for line in open(path, encoding="utf-8", errors="replace"):
        t = line.strip()
        if not t or t.startswith("v2.0") or t.startswith("#"):
            continue
        for tok in t.split():
            words.append(int(tok, 16))
    return words


def sx(v, bits=32):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) else v


def decode(ir):
    op = ir & 0x7F
    rd = (ir >> 7) & 0x1F
    f3 = (ir >> 12) & 7
    rs1 = (ir >> 15) & 0x1F
    rs2 = (ir >> 20) & 0x1F
    imm_i = sx(ir >> 20, 12)
    imm_s = sx(((ir >> 25) << 5) | ((ir >> 7) & 0x1F), 12)
    return op, rd, f3, rs1, rs2, imm_i, imm_s


def step(ir, pc, regs, mem):
    """Execute one instruction. Returns (next_pc, rd_written, value, is_ecall)."""
    op, rd, f3, rs1, rs2, imm_i, imm_s = decode(ir)
    a, b = regs[rs1], regs[rs2]
    npc = (pc + 4) & MASK
    wr, val, ecall = None, None, False

    if op == 0x33:
        if f3 == 0:
            val = (a + b) if (ir >> 30) == 0 else (a - b)
        elif f3 == 1:
            val = (a << (b & 0x1F)) & MASK
        elif f3 == 5:
            val = (a >> (b & 0x1F)) if (ir >> 30) == 0 else (sx(a) >> (b & 0x1F))
        elif f3 == 4:
            val = a ^ b
        elif f3 == 6:
            val = a | b
        elif f3 == 7:
            val = a & b
        elif f3 == 2:
            val = 1 if sx(a) < sx(b) else 0
        elif f3 == 3:
            val = 1 if a < b else 0
        val &= MASK
        wr = rd
    elif op == 0x13:
        imm = imm_i
        if f3 == 0:
            val = (a + imm) & MASK
        elif f3 == 7:
            val = a & (imm & MASK)
        elif f3 == 6:
            val = a | (imm & MASK)
        elif f3 == 4:
            val = a ^ (imm & MASK)
        elif f3 == 2:
            val = 1 if sx(a) < imm else 0
        elif f3 == 3:
            val = 1 if a < (imm & MASK) else 0
        elif f3 == 1:
            val = (a << (imm & 0x1F)) & MASK
        elif f3 == 5:
            val = (a >> (imm & 0x1F)) if (ir >> 30) == 0 else (sx(a) >> (imm & 0x1F))
        val &= MASK
        wr = rd
    elif op == 0x03:
        if f3 == 2:
            val = mem.get((a + imm_i) & MASK, 0)
        elif f3 == 0:
            byte = mem.get((a + imm_i) & MASK, 0) & 0xFF
            val = sx(byte, 8) & MASK
        elif f3 == 4:
            val = mem.get((a + imm_i) & MASK, 0) & 0xFF
        else:
            val = 0
        wr = rd
    elif op == 0x23:
        mem[(a + imm_s) & MASK] = b
    elif op == 0x63:
        take = {0: a == b, 1: a != b, 4: sx(a) < sx(b), 5: sx(a) >= sx(b),
                6: a < b, 7: a >= b}.get(f3, False)
        if take:
            imm_b = sx(((ir >> 31) << 12) | (((ir >> 7) & 1) << 11)
                       | (((ir >> 25) & 0x3F) << 5) | (((ir >> 8) & 0xF) << 1), 13)
            npc = (pc + imm_b) & MASK
    elif op == 0x6F:
        imm_j = sx(((ir >> 31) << 20) | (((ir >> 12) & 0xFF) << 12)
                   | (((ir >> 20) & 1) << 11) | (((ir >> 21) & 0x3FF) << 1), 21)
        val = (pc + 4) & MASK
        wr = rd
        npc = (pc + imm_j) & MASK
    elif op == 0x67:
        val = (pc + 4) & MASK
        wr = rd
        npc = (a + imm_i) & MASK
    elif op == 0x73:
        ecall = True
        if regs[17] == 10:
            npc = None          # halt
    if wr is not None:
        regs[wr] = val
        if wr == 0:
            regs[0] = 0
    return npc, wr, val, ecall


def main():
    trace = parse(sys.argv[1])
    rom = load_rom(sys.argv[2])
    print(f"trace rows: {len(trace)}   rom words: {len(rom)}")

    regs = [0] * 32
    mem = {}
    pc = 0
    led_seq = []

    # Build the model's per-cycle expectation by stepping the ISA model and
    # recording (pc, ir, rd_written, value) for each retired instruction.
    model = []
    guard = 0
    while pc is not None and guard < 5000:
        guard += 1
        if pc // 4 >= len(rom):
            break
        ir = rom[pc // 4]
        before = list(regs)
        npc, wr, val, ecall = step(ir, pc, regs, mem)
        if ecall and regs[17] == 34:
            led_seq.append(regs[10])
        model.append(dict(pc=pc, ir=ir, rd=wr, val=val, a0=regs[10]))
        pc = npc

    print(f"model retires {len(model)} instructions")
    print()

    # Compare cycle by cycle.  The circuit trace contains one row per clock and
    # also rows for instructions that are NOT written back (RegWrite=0), so we
    # align on (pc, ir) pairs from the model.
    print("--- first 24 cycles of the circuit vs model ---")
    print(f"{'#':>3} {'PC':>9} {'IR':>9} {'RDin':>9} {'model val':>9}  {'rd':>3}  note")
    mism = 0
    for i, r in enumerate(trace[:24]):
        mm = model[i] if i < len(model) else None
        want = f"{mm['val']:08x}" if mm and mm["val"] is not None else "     -  "
        rdw = mm["rd"] if mm and mm["rd"] is not None else "-"
        note = ""
        if mm and mm["rd"] is not None and r["rdin"] != mm["val"]:
            note = "<<< RDin differs"
            mism += 1
        if mm and r["pc"] != mm["pc"]:
            note += "  <<< PC differs"
        print(f"{i:>3} {r['pc']:09x} {r['ir']:09x} {r['rdin']:09x} {want:>9}  {rdw:>3}  {note}")

    print()
    print(f"model LED sequence: " + " ".join(f"{v:08x}" for v in led_seq))
    got = [r["led"] for r in trace if r["ir"] == 0x00000073]
    print(f"trace LED sequence: " + " ".join(f"{v:08x}" for v in got))
    print()
    print(f"RDin mismatches in the first 24 cycles: {mism}")


if __name__ == "__main__":
    main()
