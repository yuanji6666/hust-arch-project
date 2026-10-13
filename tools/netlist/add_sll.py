#!/usr/bin/env python3
"""
Add the SLL instruction decode to the CCAB single-cycle CPU circuit.

Adds one 10-input AND gate implementing the SLL minterm plus a 2-input OR gate
that splices it into the existing RegWrite net, and wires the ten decoder
literals in from the bottom ends of their buses.

Everything is placed in the region y >= 8400, which was measured to be empty
(no components, no wires; existing content ends at y = 8380).

Usage: add_sll.py <in.circ> <out.circ>
"""
import re
import sys

CIRCUIT = "◇控制信号自动生成"

# --- measured pin geometry (from Logisim's own getEnds()) -------------------
# AND gate at (x,y) with n inputs:
#   output      (x,       y)
#   inputs      (x-20, ...)  <-- see note
# Logisim reports input pins at x-20 for a size-30 gate whose loc is x.
# Observed: AND @(390,8060) has output (390,8060) and inputs (360,...).
# So inputs are at loc_x - 30 for that one, but @(380,4220) gives (350,...) = -30.
# Consistent: inputs at loc_x - 30.
AND_IN_DX = -30
OR_IN_DX = -30
# --- placement -------------------------------------------------------------
AND_LOC = (380, 8460)          # 10-input AND gate for the SLL minterm
OR_LOC = (440, 8670)           # 2-input OR gate splicing into RegWrite

# RegWrite OR gate (490,2830): bottom-most input pin is (460,2880).
# Its upstream wire chain is only 3 segments:
#   (380,3430)->(440,3430), (440,2880)->(440,3430), (440,2880)->(460,2880)
# We cut the last segment and re-route it through the new OR gate.
CUT_WIRE = '<wire from="(440,2880)" to="(460,2880)"/>'

# Literal bus bottom endpoints (measured)
BUS_TIPS = {
    "OP2": (60, 8170),
    "OP3": (80, 8200),
    "OP4": (100, 8230),
    "OP5": (120, 8260),
    "OP6": (140, 8290),
    "F12": (160, 8320),
    "F13": (180, 8350),
    "F14": (200, 8380),
    "F25": (220, 8130),
    "F30": (240, 8150),
}

# SLL minterm: ~F14 ~F13 F12 ~F25 ~F30 ~OP6 OP5 OP4 ~OP3 ~OP2
# (name, negated). Order chosen so negated literals take the upper pins and
# positive ones the lower, keeping the horizontal runs short.
SLL_INPUTS = [
    ("OP2", True),
    ("OP3", True),
    ("OP4", False),
    ("OP5", False),
    ("OP6", True),
    ("F12", False),
    ("F13", True),
    ("F14", True),
    ("F25", True),
    ("F30", True),
]


def and_input_pins(loc, n):
    """Input pin coordinates of an n-input AND gate, top to bottom."""
    x, y = loc
    before = (n - 1) if n % 2 == 1 else n // 2
    xs = x + AND_IN_DX
    pins = [(xs, y - 10 * (before - k)) for k in range(before)]
    after = n // 2
    pins += [(xs, y + 10 * (k + 1)) for k in range(after)]
    return pins


def or_input_pins(loc, n):
    x, y = loc
    before = (n - 1) if n % 2 == 1 else n // 2
    xs = x + OR_IN_DX
    pins = [(xs, y - 10 * (before - k)) for k in range(before)]
    after = n // 2
    pins += [(xs, y + 10 * (k + 1)) for k in range(after)]
    return pins


def wire(a, b):
    return f'<wire from="({a[0]},{a[1]})" to="({b[0]},{b[1]})"/>'


def build_and_gate(loc, n, negations):
    x, y = loc
    lines = [f'<comp lib="1" loc="({x},{y})" name="AND Gate">']
    lines.append('      <a name="facing" val="east"/>')
    lines.append('      <a name="width" val="1"/>')
    lines.append('      <a name="size" val="30"/>')
    lines.append(f'      <a name="inputs" val="{n}"/>')
    lines.append('      <a name="out" val="01"/>')
    lines.append('      <a name="label" val="SLL_decode"/>')
    lines.append('      <a name="labelfont" val="Dialog plain 12"/>')
    lines.append('      <a name="labelcolor" val="#000000"/>')
    for k in range(n):
        v = "true" if negations[k] else "false"
        lines.append(f'      <a name="negate{k}" val="{v}"/>')
    lines.append('    </comp>')
    return "\n    ".join(lines)


def build_or_gate(loc, n):
    x, y = loc
    lines = [f'<comp lib="1" loc="({x},{y})" name="OR Gate">']
    lines.append('      <a name="facing" val="east"/>')
    lines.append('      <a name="width" val="1"/>')
    lines.append('      <a name="size" val="30"/>')
    lines.append(f'      <a name="inputs" val="{n}"/>')
    lines.append('      <a name="out" val="01"/>')
    lines.append('      <a name="label" val=""/>')
    lines.append('      <a name="labelfont" val="Dialog plain 12"/>')
    lines.append('      <a name="labelcolor" val="#000000"/>')
    lines.append('    </comp>')
    return "\n    ".join(lines)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding="utf-8").read()

    if CUT_WIRE not in text:
        print(f"ERROR: expected wire not found: {CUT_WIRE}")
        print("The circuit layout changed; re-measure before running this.")
        sys.exit(1)

    pins = and_input_pins(AND_LOC, 10)
    neg = [n for _, n in SLL_INPUTS]

    components = [build_and_gate(AND_LOC, 10, neg), build_or_gate(OR_LOC, 2)]

    wires = []

    # 1) literal buses -> AND gate inputs
    for (name, _), pin in zip(SLL_INPUTS, pins):
        bx, by = BUS_TIPS[name]
        # bus tip down to the row of this input pin
        wires.append(wire((bx, by), (bx, pin[1])))
        # across to the gate input
        wires.append(wire((bx, pin[1]), pin))

    # 2) AND output -> OR gate top input
    orpins = or_input_pins(OR_LOC, 2)
    ax, ay = AND_LOC
    wires.append(wire((ax, ay), (orpins[0][0], ay)))
    wires.append(wire((orpins[0][0], ay), orpins[0]))

    # 3) old RegWrite chain end (440,2880) -> OR gate bottom input.
    #    x=440 below y~3430 is free (measured), so run straight down.
    bottom = orpins[1]
    wires.append(wire((440, 2880), (440, bottom[1])))
    wires.append(wire((440, bottom[1]), bottom))

    # 4) OR output (460,8670) -> back up to the RegWrite OR gate input (460,2880).
    #    x=460 below y=2880 is free (measured), so one straight vertical wire.
    ox, oy = OR_LOC
    wires.append(wire((ox + 20, oy), (460, 2880)))

    block = []
    block.append("    " + "\n    ".join(components))
    block.append("    " + "\n    ".join(wires))

    # cut the old wire and append the new block at the end of the circuit
    text = text.replace("    " + CUT_WIRE + "\n", "", 1)
    if CUT_WIRE in text:
        text = text.replace(CUT_WIRE + "\n", "", 1)

    # find the target circuit element and insert before its closing tag
    m = re.search(r'<circuit name="' + re.escape(CIRCUIT) + r'">', text)
    if not m:
        print(f"ERROR: circuit not found: {CIRCUIT}")
        sys.exit(1)
    start = m.end()
    close = text.find("</circuit>", start)
    if close < 0:
        print("ERROR: closing </circuit> not found")
        sys.exit(1)

    insertion = "\n    " + block[0] + "\n    " + block[1] + "\n  "
    text = text[:close] + insertion + text[close:]

    open(dst, "w", encoding="utf-8", newline="").write(text)
    print(f"wrote {dst}")
    print(f"  AND gate {AND_LOC} inputs: {pins}")
    print(f"  OR gate  {OR_LOC} inputs: {or_input_pins(OR_LOC, 2)}")
    print(f"  wires added: {len(wires)}")
    print(f"  cut wire: {CUT_WIRE}")


if __name__ == "__main__":
    main()
