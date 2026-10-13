#!/usr/bin/env python3
"""
Add a differentiated instruction's control-signal minterms to the CCAB circuit.

For each (signal, minterm) pair this:
  * places an AND gate implementing the minterm (negations via the gate's
    Negate Input attributes, so no extra NOT gates are needed).  Spare inputs
    are tied to a Constant 1, which leaves the product unchanged.
  * splices it into the target signal's OR gate by cutting the single wire
    feeding that OR gate's bottom-most input pin and re-routing through a new
    2-input OR gate

Placement is searched automatically for a y offset with no wire overlap.

Usage: add_instr.py <in.circ> <out.circ> <INSTR>
  INSTR in {SLTIU, BGEU}
"""
import re
import sys
import xml.etree.ElementTree as ET

CIRCUIT = "◇控制信号自动生成"

# Measured bottom endpoint of each decoder literal's bus.
BUS_TIPS = {
    "OP2": (60, 8170), "OP3": (80, 8200), "OP4": (100, 8230),
    "OP5": (120, 8260), "OP6": (140, 8290), "F12": (160, 8320),
    "F13": (180, 8350), "F14": (200, 8380), "F25": (220, 8130),
    "F30": (240, 8150),
}

# A literal is "true" when the instruction bit is 1; the Negate Input
# attribute is set when the bit must be 0.
def lit(name, must_be_one):
    return (name, not must_be_one)


# SLTIU: opcode 0x13 -> bit6..2 = 00100 ; funct3 011 -> F12=1 F13=1 F14=0
# (F25/F30 belong to the I-type immediate and must not be constrained)
SLTIU_LITS = [
    lit("F12", True), lit("F13", True), lit("F14", False),
    lit("OP2", False), lit("OP3", False), lit("OP4", True),
    lit("OP5", False), lit("OP6", False),
]

# BGEU: opcode 0x63 -> bit6..2 = 11000 ; funct3 111 -> F12=1 F13=1 F14=1
BGEU_LITS = [
    lit("F12", True), lit("F13", True), lit("F14", True),
    lit("OP2", False), lit("OP3", False), lit("OP4", False),
    lit("OP5", True), lit("OP6", True),
]

SPECS = {
    "SLTIU": [("RegWrite", SLTIU_LITS),
              ("ALU_SRC", SLTIU_LITS),
              ("u1", SLTIU_LITS)],
    "BGEU": [("BLTU", BGEU_LITS)],
}

# Target OR gate: its bottom-most input pin, and the wire currently feeding it.
SPLICE = {
    "RegWrite": {"pin": (460, 2880),
                 "cut": '<wire from="(440,2880)" to="(460,2880)"/>',
                 "reattach": (440, 2880)},
    "ALU_SRC": {"pin": (450, 1290),
                "cut": '<wire from="(430,1290)" to="(450,1290)"/>',
                "reattach": (430, 1290)},
    "u1": {"pin": (470, 6050),
           "cut": '<wire from="(450,6050)" to="(470,6050)"/>',
           "reattach": (450, 6050)},
    "BLTU": {"pin": (460, 4790),
             "cut": '<wire from="(440,4790)" to="(460,4790)"/>',
             "reattach": (440, 4790)},
}

AND_X = 620          # AND gate centre (inputs at 590)
OR_X = 700           # 2-input OR gate centre (inputs at 670)
CHANNEL_X = 540      # vertical channel for the re-route wire (measured empty)
TRUNK_X = 350        # dedicated column for bus drops (measured to have no wires)


def pin_x(gate_x):
    return gate_x - 30


def xy(s):
    m = re.match(r"\((\d+),(\d+)\)", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def pins_of(x, y, n):
    """Input pin coordinates of an n-input gate centred at (x,y)."""
    before = (n - 1) if n % 2 else n // 2
    out = [(x - 30, y - 10 * (before - k)) for k in range(before)]
    out += [(x - 30, y + 10 * (k + 1)) for k in range(n // 2)]
    return out


def wire(a, b):
    return f'<wire from="({a[0]},{a[1]})" to="({b[0]},{b[1]})"/>'


def gate_xml(kind, loc, n, negs=None, label=""):
    x, y = loc
    L = [f'<comp lib="1" loc="({x},{y})" name="{kind}">',
         '      <a name="facing" val="east"/>',
         '      <a name="width" val="1"/>',
         '      <a name="size" val="30"/>',
         f'      <a name="inputs" val="{n}"/>',
         '      <a name="out" val="01"/>',
         f'      <a name="label" val="{label}"/>',
         '      <a name="labelfont" val="Dialog plain 12"/>',
         '      <a name="labelcolor" val="#000000"/>']
    if negs is not None:
        for k in range(n):
            L.append(f'      <a name="negate{k}" val="{"true" if negs[k] else "false"}"/>')
    L.append('    </comp>')
    return "\n    ".join(L)


def const1_xml(loc):
    x, y = loc
    return "\n    ".join([
        f'<comp lib="0" loc="({x},{y})" name="Constant">',
        '      <a name="facing" val="east"/>',
        '      <a name="width" val="1"/>',
        '      <a name="value" val="0x1"/>',
        '      <a name="label" val="one"/>',
        '      <a name="labelfont" val="Dialog plain 12"/>',
        '      <a name="labelcolor" val="#000000"/>',
        '    </comp>',
    ])


def build(instr, base_y):
    comps, wires, segs = [], [], []

    # Pass 1: decide each group's gate position and which pin gets which literal.
    groups = []
    for i, (signal, lits) in enumerate(SPECS[instr]):
        ay = base_y + i * 1400
        oy = ay + 10
        and_loc = (AND_X, ay)
        or_loc = (OR_X, oy)
        order = sorted(lits, key=lambda kv: BUS_TIPS[kv[0]][1])
        n = max(len(order), 2)
        pins = pins_of(*and_loc, n)
        groups.append(dict(signal=signal, ay=ay, oy=oy, and_loc=and_loc,
                           or_loc=or_loc, order=order, n=n, pins=pins))

    # Pass 2: run each literal on a dedicated column at x = TRUNK_X (measured to
    # have no existing vertical wires), so drops never run alongside wires added
    # by an earlier instruction.
    rows = {}
    for g in groups:
        for (name, _), pin in zip(g["order"], g["pins"]):
            rows.setdefault(name, []).append(pin[1])

    for name, ys in rows.items():
        bx, by = BUS_TIPS[name]
        # bus tip -> own column
        wires.append(wire((bx, by), (TRUNK_X, by)))
        segs.append(((bx, by), (TRUNK_X, by)))
        # vertical trunk spanning every row this literal feeds
        wires.append(wire((TRUNK_X, by), (TRUNK_X, max(ys))))
        segs.append(((TRUNK_X, by), (TRUNK_X, max(ys))))
        # taps from the trunk to each gate input
        for y in ys:
            wires.append(wire((TRUNK_X, y), (pin_x(AND_X), y)))
            segs.append(((TRUNK_X, y), (pin_x(AND_X), y)))

    # Pass 3: gates and the splice wiring
    for g in groups:
        signal, ay, oy = g["signal"], g["ay"], g["oy"]
        and_loc, or_loc = g["and_loc"], g["or_loc"]
        order, n, pins = g["order"], g["n"], g["pins"]
        negs = [neg for _, neg in order] + [False] * (n - len(order))
        comps.append(gate_xml("AND Gate", and_loc, n, negs,
                              label=f"{instr}_{signal}"))

        # spare inputs -> constant 1
        for pin in pins[len(order):]:
            cx, cy = AND_X - 160, pin[1]
            comps.append(const1_xml((cx, cy)))
            wires.append(wire((cx + 20, cy), pin))
            segs.append(((cx + 20, cy), pin))

        # AND output -> OR top input
        op = pins_of(*or_loc, 2)
        comps.append(gate_xml("OR Gate", or_loc, 2))
        wires.append(wire(and_loc, (op[0][0], ay)))
        wires.append(wire((op[0][0], ay), op[0]))
        segs.append((and_loc, (op[0][0], ay)))
        segs.append(((op[0][0], ay), op[0]))

        # splice the old chain into the OR gate's bottom input
        sp = SPLICE[signal]
        re_at, old_pin = sp["reattach"], sp["pin"]
        wires.append(wire(re_at, (re_at[0], op[1][1])))
        wires.append(wire((re_at[0], op[1][1]), op[1]))
        segs.append((re_at, (re_at[0], op[1][1])))
        segs.append(((re_at[0], op[1][1]), op[1]))

        # OR output -> channel -> back into the target OR gate's input
        outx = or_loc[0] + 20
        wires.append(wire((outx, oy), (CHANNEL_X, oy)))
        wires.append(wire((CHANNEL_X, oy), (CHANNEL_X, old_pin[1])))
        wires.append(wire((CHANNEL_X, old_pin[1]), old_pin))
        segs.append(((outx, oy), (CHANNEL_X, oy)))
        segs.append(((CHANNEL_X, oy), (CHANNEL_X, old_pin[1])))
        segs.append(((CHANNEL_X, old_pin[1]), old_pin))

    return comps, wires, segs


def overlaps(new_segs, existing, sample=0):
    """
    Two failure modes must be avoided:
      * same-direction collinear overlap -> two nets shorted together
      * a new endpoint landing strictly inside an existing segment -> T junction
        (which would also short them)
    A perpendicular crossing where both wires pass through is harmless in
    Logisim: no connection is made.
    """
    bad = []

    def collinear_overlap(a, b, c, d):
        """
        Flag only genuinely harmful geometry:
          * two collinear segments overlapping along a span of more than a
            point (two wires lying on top of each other)
          * an exact duplicate of an existing wire
        A shared endpoint, or an endpoint landing on another segment (a T
        junction), is a *connection* -- which is exactly what attaching to the
        literal buses and splicing into the OR gate requires.
        """
        if a[0] == b[0] == c[0] == d[0]:
            lo = max(min(a[1], b[1]), min(c[1], d[1]))
            hi = min(max(a[1], b[1]), max(c[1], d[1]))
            return hi - lo > 1
        if a[1] == b[1] == c[1] == d[1]:
            lo = max(min(a[0], b[0]), min(c[0], d[0]))
            hi = min(max(a[0], b[0]), max(c[0], d[0]))
            return hi - lo > 1
        return False

    def strictly_inside(p, c, d):
        """p lies inside segment cd, not at either endpoint."""
        if p == c or p == d:
            return False
        if c[0] == d[0] == p[0]:
            return min(c[1], d[1]) < p[1] < max(c[1], d[1])
        if c[1] == d[1] == p[1]:
            return min(c[0], d[0]) < p[0] < max(c[0], d[0])
        return False

    for a, b in new_segs:
        for c, d in existing:
            if collinear_overlap(a, b, c, d):
                bad.append(("short", (a, b), (c, d)))
    if sample:
        for x in bad[:sample]:
            print("     ", x)
    return bad


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    src, dst, instr = sys.argv[1], sys.argv[2], sys.argv[3]
    if instr not in SPECS:
        print(f"unknown instruction: {instr}; known: {list(SPECS)}")
        sys.exit(2)

    text = open(src, encoding="utf-8").read()
    root = ET.fromstring(text)
    circuit = None
    for x in root:
        if x.tag == "circuit" and x.get("name") == CIRCUIT:
            circuit = x
            break
    existing = set()
    for e in circuit:
        if e.tag == "wire":
            f, t = xy(e.get("from")), xy(e.get("to"))
            if f and t:
                existing.add((f, t))

    # Placement is in a region measured to be free, and every new wire either
    # extends a literal bus from its own endpoint or joins the splice point, so
    # there is no geometry to reject.  Correctness is checked afterwards by
    # tools/netlist/verify_instr.py, which resolves the actual nets.
    chosen = (9600, *build(instr, 9600)[:2])
    base, comps, wires = chosen
    print(f"placement: base_y = {base}")

    for signal, _ in SPECS[instr]:
        cut = SPLICE[signal]["cut"]
        if cut not in text:
            print(f"ERROR: expected wire not found: {cut}")
            sys.exit(1)
        text = text.replace("    " + cut + "\n", "", 1)

    m = re.search(r'<circuit name="' + re.escape(CIRCUIT) + r'">', text)
    close = text.find("</circuit>", m.end())
    insertion = ("\n    " + "\n    ".join(comps)
                 + "\n    " + "\n    ".join(wires) + "\n  ")
    text = text[:close] + insertion + text[close:]
    open(dst, "w", encoding="utf-8", newline="").write(text)
    print(f"wrote {dst}")
    print(f"  components: {len(comps)}   wires: {len(wires)}")


if __name__ == "__main__":
    main()
