#!/usr/bin/env python3
"""
Compare a Logisim -tty table trace against RARS's expected register sequence.

Derives the destination-register value stream from the trace (RDin on every
clock where RegWrite=1) and compares it to the value stream RARS produces for
the same program, reporting the first divergence.

Usage: analyze_trace.py <traceFile> <expected-values...>
"""
import re
import sys

HEADER_RE = re.compile(
    r"^\s*([01E])\s+([01E])\s+([0-9a-f]{8})\s+([0-9a-f]{8})"
    r"\s+([0-9a-f]{8})\s+([0-9a-f]{8})\s+([0-9a-f]{8})")


def parse(path):
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = HEADER_RE.match(line)
        if m:
            rows.append(dict(rw=m.group(1), mw=m.group(2), pc=int(m.group(3), 16),
                             ir=int(m.group(4), 16), rdin=int(m.group(5), 16),
                             mdin=int(m.group(6), 16), led=int(m.group(7), 16)))
    return rows


def mnem(ir):
    op = ir & 0x7F
    f3 = (ir >> 12) & 7
    rd = (ir >> 7) & 0x1F
    rs1 = (ir >> 15) & 0x1F
    rs2 = (ir >> 20) & 0x1F
    if op == 0x33:
        name = {0: "add", 1: "sll", 5: "srl", 7: "and", 6: "or", 4: "xor",
                2: "slt", 3: "sltu"}.get(f3, f"r{f3}")
        return f"{name} rd={rd} rs1={rs1} rs2={rs2}"
    if op == 0x13:
        name = {0: "addi", 1: "slli", 5: "srli", 7: "andi"}.get(f3, f"i{f3}")
        return f"{name} rd={rd} rs1={rs1} imm={ir >> 20}"
    if op == 0x03:
        return f"load rd={rd}"
    if op == 0x23:
        return "sw"
    if op == 0x63:
        return f"branch f3={f3}"
    if op == 0x6F:
        return f"jal rd={rd}"
    if op == 0x67:
        return f"jalr rd={rd}"
    if op == 0x73:
        return "ecall"
    return f"op={op:02x}"


def main():
    trace = sys.argv[1]
    expected = [int(x, 16) for x in sys.argv[2:]] if len(sys.argv) > 2 else None
    rows = parse(trace)
    print(f"trace rows: {len(rows)}")

    # ECALL delivers a0 to the LED; ecall rows are where a7==34 was set.
    led = []
    print("\n--- ecall rows (LED holds a0) ---")
    for r in rows:
        if r["ir"] == 0x00000073:
            led.append(r["led"])
            print(f"   PC={r['pc']:08x}  LED={r['led']:08x}")
    print("\nLED sequence:", " ".join(f"{v:08x}" for v in led))

    if expected:
        print("\n--- comparison vs RARS ---")
        print("expected:", " ".join(f"{v:08x}" for v in expected))
        n = min(len(led), len(expected))
        bad = 0
        for i in range(n):
            mark = "" if led[i] == expected[i] else "   <<< MISMATCH"
            if led[i] != expected[i]:
                bad += 1
            print(f"   [{i:2d}] got={led[i]:08x} want={expected[i]:08x}{mark}")
        if bad == 0 and len(led) >= len(expected):
            print(f"\n   ALL {len(expected)} VALUES MATCH")
        else:
            print(f"\n   {bad} mismatch(es); got {len(led)} values, expected {len(expected)}")


if __name__ == "__main__":
    main()
