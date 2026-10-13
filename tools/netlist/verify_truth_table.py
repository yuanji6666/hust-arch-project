#!/usr/bin/env python3
"""
Verify a Logisim control-signal truth table against the RISC-V specification.

The truth table is produced by tools/netlist/TruthTable.java, which drives the
circuit through Logisim's own simulator and enumerates all 2^10 input
combinations. This script independently derives the expected control signals
from the RISC-V encoding and diffs the two.

Signal legend (as produced by the circuit):
  inputs : F12 F13 F14 F25 F30 OP2 OP3 OP4 OP5 OP6
  outputs: ALU_SRC BEQ BLTU BNE JAL JALR LB MemToReg MemWrite RegWrite
           S_Type U_Type csr ecall u1 u2

Usage: verify_truth_table.py <truth.csv> [--instr NAME]
"""
import argparse
import csv
import sys

INPUTS = ["F12", "F13", "F14", "F25", "F30", "OP2", "OP3", "OP4", "OP5", "OP6"]

# R-type and I-type ALU opcodes
OP_R = 0b0110011
OP_I = 0b0010011
OP_LOAD = 0b0000011
OP_STORE = 0b0100011
OP_BRANCH = 0b1100011
OP_JAL = 0b1101111
OP_JALR = 0b1100111
OP_LUI = 0b0110111
OP_SYSTEM = 0b1110011


def enc_r(funct7, rs2, rs1, funct3, rd, opcode):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def enc_i(imm, rs1, funct3, rd, opcode):
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def enc_s(imm, rs2, rs1, funct3, opcode):
    imm &= 0xFFF
    return ((imm >> 5) << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | ((imm & 0x1F) << 7) | opcode


def enc_b(imm, rs2, rs1, funct3, opcode):
    imm &= 0x1FFF
    b12 = (imm >> 12) & 1
    b11 = (imm >> 11) & 1
    b10_5 = (imm >> 5) & 0x3F
    b4_1 = (imm >> 1) & 0xF
    return (b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) \
        | (b4_1 << 8) | (b11 << 7) | opcode


def enc_j(imm, rd, opcode):
    imm &= 0x1FFFFF
    b20 = (imm >> 20) & 1
    b10_1 = (imm >> 1) & 0x3FF
    b11 = (imm >> 11) & 1
    b19_12 = (imm >> 12) & 0xFF
    return (b20 << 31) | (b19_12 << 12) | (b11 << 20) | (b10_1 << 21) | (rd << 7) | opcode


def enc_u(imm20, rd, opcode):
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | opcode


def fields(word):
    """Extract the 10 decoder inputs from an instruction word.

    F12/F13/F14 are bits 0/1/2 of funct3 (or of the branch immediate for B-type,
    where those bits carry imm[2:0]); the circuit taps bits 12/13/14 directly.
    F25/F30 are bit 25/30 of the raw instruction.
    """
    return {
        "F12": (word >> 12) & 1,
        "F13": (word >> 13) & 1,
        "F14": (word >> 14) & 1,
        "F25": (word >> 25) & 1,
        "F30": (word >> 30) & 1,
        "OP2": (word >> 2) & 1,
        "OP3": (word >> 3) & 1,
        "OP4": (word >> 4) & 1,
        "OP5": (word >> 5) & 1,
        "OP6": (word >> 6) & 1,
    }


# Expected control signals per instruction.
# Only signals asserted by this circuit are listed; everything else is 0.
# u1/u2 encode the immediate type; values below are what the design uses.
EXPECT = {
    # name: (word, {signal: 1, ...})
    "add":     (enc_r(0b0000000, 0, 0, 0b000, 0, OP_R), {"RegWrite": 1}),
    "sub":     (enc_r(0b0100000, 0, 0, 0b000, 0, OP_R), {"RegWrite": 1}),
    "and":     (enc_r(0b0000000, 0, 0, 0b111, 0, OP_R), {"RegWrite": 1}),
    "or":      (enc_r(0b0000000, 0, 0, 0b110, 0, OP_R), {"RegWrite": 1}),
    "xor":     (enc_r(0b0000000, 0, 0, 0b100, 0, OP_R), {"RegWrite": 1}),
    "sll":     (enc_r(0b0000000, 0, 0, 0b001, 0, OP_R), {"RegWrite": 1}),
    "srl":     (enc_r(0b0000000, 0, 0, 0b101, 0, OP_R), {"RegWrite": 1}),
    "sra":     (enc_r(0b0100000, 0, 0, 0b101, 0, OP_R), {"RegWrite": 1}),
    "slt":     (enc_r(0b0000000, 0, 0, 0b010, 0, OP_R), {"RegWrite": 1}),
    "sltu":    (enc_r(0b0000000, 0, 0, 0b011, 0, OP_R), {"RegWrite": 1}),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--instr", action="append", default=None,
                    help="restrict to these instruction names")
    args = ap.parse_args()

    table = {}
    with open(args.csv, newline="", encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        for row in rd:
            key = tuple(int(row[k]) for k in INPUTS)
            table[key] = row

    print(f"loaded {len(table)} rows from {args.csv}")

    names = args.instr if args.instr else list(EXPECT)
    mismatches = 0
    for name in names:
        if name not in EXPECT:
            print(f"  {name:8s}  (no expectation defined)")
            continue
        word, exp = EXPECT[name]
        f = fields(word)
        key = tuple(f[k] for k in INPUTS)
        row = table.get(key)
        if row is None:
            print(f"  {name:8s} MISSING row for {key}")
            mismatches += 1
            continue
        got = {k: int(row[k]) for k in row if k not in INPUTS}
        # expected: listed signals = 1, all others 0
        want = {k: 1 if k in exp else 0 for k in got}
        bad = {k: (want[k], got[k]) for k in got if want[k] != got[k]}
        status = "OK" if not bad else "DIFF"
        if bad:
            mismatches += 1
        print(f"  {name:8s} {word:08x}  {status}")
        if bad:
            for k, (w, g) in sorted(bad.items()):
                print(f"        {k:10s} expected={w} got={g}")
    print()
    print(f"{mismatches} instruction(s) differ")


if __name__ == "__main__":
    main()
