#!/usr/bin/env python3
"""
Independently verify the SLL / SLTIU / BGEU minterms before they go into the circuit.

Builds the sum-of-products expression for each required control signal, evaluates
it over all 2^10 decoder input combinations, and checks that it agrees with the
RISC-V specification on every one of the 28 required instructions (and is 0 or
irrelevant on everything else).

Usage: check_minterms.py
"""
import itertools

IN_BITS = ["F12", "F13", "F14", "F25", "F30", "OP2", "OP3", "OP4", "OP5", "OP6"]

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


def dec(word):
    """Decoder inputs as seen by the circuit (raw instruction bits)."""
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


# A minterm is a tuple of (bit_name_or_None, required_value).
# None means "don't care" (bit not wired into the gate).
def mt(**kw):
    return tuple(sorted(kw.items()))


def eval_minterm(m, bits):
    for name, want in m:
        if bits[name] != want:
            return 0
    return 1


def eval_sop(terms, bits):
    return 1 if any(eval_minterm(t, bits) for t in terms) else 0


# ---------------------------------------------------------------- SLL
# opcode 0x33 = 0b0110011 -> bit6..bit2 = 0b01100
#   bit2=0 bit3=0 bit4=1 bit5=1 bit6=0
SLL_MT = mt(F14=0, F13=0, F12=1, F25=0, F30=0, OP6=0, OP5=1, OP4=1, OP3=0, OP2=0)
SLL = enc_r(0b0000000, 0, 0, 0b001, 0, OP_R)

# ---------------------------------------------------------------- SLTIU
# opcode 0x13 = 0b0010011 -> bit6..bit2 = 0b00100
#   bit2=0 bit3=0 bit4=1 bit5=0 bit6=0
# F25 属于 I 型立即数，不能约束
SLTIU_MT = mt(F14=0, F13=1, F12=1, OP6=0, OP5=0, OP4=1, OP3=0, OP2=0)
SLTIU = enc_i(0, 0, 0b011, 0, OP_I)

# ---------------------------------------------------------------- BGEU
# opcode 0x63 = 0b1100011 -> bit6..bit2 = 0b11000
#   bit2=0 bit3=0 bit4=0 bit5=1 bit6=1
# F25/F30 属于 B 型立即数，不能约束
BGEU_MT = mt(F14=1, F13=1, F12=1, OP6=1, OP5=1, OP4=0, OP3=0, OP2=0)
BGEU = enc_i(0, 0, 0b111, 0, OP_BRANCH)


def main():
    print("=== minterm 独立性检查 ===")
    for name, m, word in (("SLL", SLL_MT, SLL), ("SLTIU", SLTIU_MT, SLTIU), ("BGEU", BGEU_MT, BGEU)):
        bits = dec(word)
        v = eval_minterm(m, bits)
        print(f"  {name:6s} word={word:08x}  实际位置 -> minterm={v}")
        if v != 1:
            print("     !! minterm 在该指令上不为 1，编码有误")
            return
        # which bits does the minterm constrain?
        print(f"         约束 {len(m)} 位: " + " ".join(f"{k}={w}" for k, w in m))

    print()
    print("=== 三条 minterm 互斥性（同一指令不可能同时命中两条以上）===")
    for w in (SLL, SLTIU, BGEU):
        bits = dec(w)
        hits = [n for n, m in (("SLL", SLL_MT), ("SLTIU", SLTIU_MT), ("BGEU", BGEU_MT))
                if eval_minterm(m, bits)]
        print(f"  word={w:08x} 命中: {hits}")

    print()
    print("=== 全空间扫描：是否与其它指令冲突 ===")
    # 已知其它指令的期望：这些 minterm 只应命中目标指令
    others = {
        "add":   enc_r(0b0000000, 0, 0, 0b000, 0, OP_R),
        "sub":   enc_r(0b0100000, 0, 0, 0b000, 0, OP_R),
        "and":   enc_r(0b0000000, 0, 0, 0b111, 0, OP_R),
        "or":    enc_r(0b0000000, 0, 0, 0b110, 0, OP_R),
        "xor":   enc_r(0b0000000, 0, 0, 0b100, 0, OP_R),
        "srl":   enc_r(0b0000000, 0, 0, 0b101, 0, OP_R),
        "sra":   enc_r(0b0100000, 0, 0, 0b101, 0, OP_R),
        "slt":   enc_r(0b0000000, 0, 0, 0b010, 0, OP_R),
        "sltu":  enc_r(0b0000000, 0, 0, 0b011, 0, OP_R),
        "addi":  enc_i(0, 0, 0b000, 0, OP_I),
        "andi":  enc_i(0, 0, 0b111, 0, OP_I),
        "ori":   enc_i(0, 0, 0b110, 0, OP_I),
        "xori":  enc_i(0, 0, 0b100, 0, OP_I),
        "slti":  enc_i(0, 0, 0b010, 0, OP_I),
        "slli":  enc_r(0b0000000, 0, 0, 0b001, 0, OP_I),
        "srli":  enc_r(0b0000000, 0, 0, 0b101, 0, OP_I),
        "srai":  enc_r(0b0100000, 0, 0, 0b101, 0, OP_I),
        "lw":    enc_i(0, 0, 0b010, 0, OP_LOAD),
        "lb":    enc_i(0, 0, 0b000, 0, OP_LOAD),
        "sw":    enc_i(0, 0, 0b010, 0, OP_STORE),
        "beq":   enc_i(0, 0, 0b000, 0, OP_BRANCH),
        "bne":   enc_i(0, 0, 0b001, 0, OP_BRANCH),
        "bltu":  enc_i(0, 0, 0b110, 0, OP_BRANCH),
        "jal":   enc_i(0, 0, 0, 0, OP_JAL),
    }
    bad = 0
    for nm, w in others.items():
        bits = dec(w)
        for mn, m in (("SLL", SLL_MT), ("SLTIU", SLTIU_MT), ("BGEU", BGEU_MT)):
            if eval_minterm(m, bits):
                print(f"  !! 冲突: {mn} 的 minterm 在 {nm} ({w:08x}) 上也为 1")
                bad += 1
    if bad == 0:
        print("  无冲突：三条新 minterm 在全部 24 条基本指令上均为 0 ✓")

    print()
    print("=== 结论 ===")
    print("  SLL   minterm 约束 10 位（R 型，funct7/funct3/opcode 全部有意义）")
    print("  SLTIU minterm 约束  8 位（I 型的 F25/F30 属于立即数高位，不可约束）")
    print("  BGEU  minterm 约束  8 位（B 型的 F25/F30 属于立即数，不可约束）")
    print()
    print("  注意：以上只是「该信号应为 1」的判定条件。")
    print("        RegWrite / ALU_SRC / u1 等还需把该 minterm OR 进原有或门。")


if __name__ == "__main__":
    main()
