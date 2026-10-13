#!/usr/bin/env python3
"""
Verify the SLL decode added to the CCAB circuit is wired correctly.

Builds a net model from Logisim's exact pin locations and checks:
  1. each new AND gate input is connected to the intended decoder literal
  2. the new AND gate output reaches the new OR gate
  3. the old RegWrite chain is spliced through the new OR gate
  4. the new OR gate output reaches the RegWrite OR gate's input pin

Usage: verify_sll.py <modified.circ>
"""
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

CIRCUIT = "◇控制信号自动生成"
AND_LOC = (380, 8460)
OR_LOC = (440, 8670)
REGW_OR_IN = (460, 2880)          # RegWrite OR gate's bottom input pin
OLD_CHAIN_END = (440, 2880)       # where the cut wire used to attach

BUS_TIPS = {
    "OP2": (60, 8170), "OP3": (80, 8200), "OP4": (100, 8230),
    "OP5": (120, 8260), "OP6": (140, 8290), "F12": (160, 8320),
    "F13": (180, 8350), "F14": (200, 8380), "F25": (220, 8130),
    "F30": (240, 8150),
}
SLL_INPUTS = [
    ("OP2", True), ("OP3", True), ("OP4", False), ("OP5", False), ("OP6", True),
    ("F12", False), ("F13", True), ("F14", True), ("F25", True), ("F30", True),
]


def xy(s):
    m = re.match(r"\((\d+),(\d+)\)", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


class Net:
    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def and_pins(loc, n):
    x, y = loc
    before = (n - 1) if n % 2 else n // 2
    out = [(x - 30, y - 10 * (before - k)) for k in range(before)]
    out += [(x - 30, y + 10 * (k + 1)) for k in range(n // 2)]
    return out


def main():
    path = sys.argv[1]
    root = ET.parse(path).getroot()
    c = None
    for x in root:
        if x.tag == "circuit" and x.get("name") == CIRCUIT:
            c = x
            break
    if c is None:
        print("circuit not found")
        sys.exit(1)

    net = Net()

    # every wire endpoint joins
    wires = []
    for e in c:
        if e.tag != "wire":
            continue
        f, t = xy(e.get("from")), xy(e.get("to"))
        if f and t:
            wires.append((f, t))
            net.union(f, t)

    # collinear touching segments must also join (T junctions)
    def on_seg(p, a, b):
        if a[0] == b[0] == p[0]:
            return min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
        if a[1] == b[1] == p[1]:
            return min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
        return False

    for f, t in wires:
        for p in (f, t):
            for f2, t2 in wires:
                if on_seg(p, f2, t2):
                    net.union(p, f2)

    # collect component pins
    pins = []          # (name, loc, kind, label)
    for e in c:
        if e.tag != "comp":
            continue
        name = e.get("name")
        attrs = {a.get("name"): a.get("val") for a in e.findall("a")}
        loc = xy(e.get("loc"))
        if name in ("AND Gate", "OR Gate", "NAND Gate"):
            pins.append((name, loc, "out", ""))
            n = int(attrs.get("inputs", "2"))
            for p in and_pins(loc, n):
                pins.append((name, p, "in", ""))
        elif name == "NOT Gate":
            pins.append((name, loc, "out", ""))
            pins.append((name, (loc[0] - 20, loc[1]), "in", ""))
        elif name == "Pin":
            pins.append((name, loc, "pin",
                         attrs.get("label", "")))
            pins.append((name, loc, "pin", attrs.get("label", "")))

    # which component pins sit on a net
    on_net = defaultdict(list)
    for name, loc, kind, label in pins:
        on_net[net.find(loc)].append((name, loc, kind, label))

    def net_of(loc):
        return net.find(loc)

    print(f"=== verifying {path} ===")
    print(f"    wires={len(wires)}  nets={len(set(net.find(f) for f, _ in wires))}")

    ok = True

    # --- 1) AND inputs -> intended literals
    apins = and_pins(AND_LOC, 10)
    print()
    print("1) 新增与门的 10 个输入是否各接到正确的字面量总线")
    for k, (pin, (name, neg)) in enumerate(zip(apins, SLL_INPUTS)):
        tip = BUS_TIPS[name]
        same = net_of(pin) == net_of(tip)
        # the literal bus is driven by an input Pin with that label
        drivers = [d for d in on_net[net_of(pin)] if d[0] == "Pin"]
        labels = sorted(set(d[3] for d in drivers if d[3]))
        status = "OK" if same else "MISMATCH"
        if not same:
            ok = False
        print(f"     引脚{pin} <- {name:5s} (取反={neg})  "
              f"与总线{tip}同网={same}  {status}  网络上的Pin: {labels}")

    # --- 2) AND output -> OR gate
    ax, ay = AND_LOC
    ox, oy = OR_LOC
    or_pins = [(ox - 30, oy - 10), (ox - 30, oy + 10)]
    print()
    print("2) 与门输出是否到达新或门")
    reach = net_of((ax, ay)) == net_of(or_pins[0]) or net_of((ax, ay)) == net_of(or_pins[1])
    print(f"     与门输出 {(ax,ay)} -> 新或门输入 {or_pins}  同网={reach}")
    ok = ok and reach

    # --- 3) old RegWrite chain end spliced into OR gate
    print()
    print("3) 原 RegWrite 链末端是否接入新或门")
    spliced = net_of(OLD_CHAIN_END) == net_of(or_pins[0]) or net_of(OLD_CHAIN_END) == net_of(or_pins[1])
    print(f"     原链末端 {OLD_CHAIN_END} -> 新或门输入 {or_pins}  同网={spliced}")
    ok = ok and spliced

    # --- 4) OR output -> RegWrite OR gate input
    print()
    print("4) 新或门输出是否接到 RegWrite 或门的输入引脚")
    to_regw = net_of((ox + 20, oy)) == net_of(REGW_OR_IN)
    print(f"     新或门输出 {(ox+20,oy)} -> RegWrite 或门输入 {REGW_OR_IN}  同网={to_regw}")
    ok = ok and to_regw

    # --- 5) safety: the removed wire must be gone
    print()
    print("5) 安全检查")
    gone = not any((a == OLD_CHAIN_END and b == REGW_OR_IN) or (b == OLD_CHAIN_END and a == REGW_OR_IN)
                   for a, b in wires)
    print(f"     原导线 {OLD_CHAIN_END}->{REGW_OR_IN} 已删除 = {gone}")
    ok = ok and gone

    # two drivers on the RegWrite net would be a conflict
    regw_net = on_net[net_of(REGW_OR_IN)]
    out_drivers = [d for d in regw_net if d[0] == "OR Gate"]
    print(f"     RegWrite 网上的 OR Gate 数量 = {len(out_drivers)}  (应为 1，多则为冲突)")
    ok = ok and len(out_drivers) == 1

    print()
    print("=== 结论:", "全部通过 ✓" if ok else "存在问题 ✗", "===")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
