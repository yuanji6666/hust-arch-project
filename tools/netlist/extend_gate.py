#!/usr/bin/env python3
"""
Extend an AND/OR gate's input count inside a Logisim .circ and remap every wire
attached to its input pins.

Logisim's gate pin geometry, verified against Logisim's own createComponent
(see tools/netlist/GateGeom.java):

    even n : inputs at  y-k*10 for k = n/2 .. 1, then y+k*10 for k = 1 .. n/2
             (no pin at y+0)
    odd  n : inputs at  y-k*10 for k = (n-1)/2 .. 1, then y+0,
             then y+k*10 for k = 1 .. (n-1)/2

Changing n therefore shifts every existing pin, so all attached wires must be
rewritten.  The rewrite is done by: collect the wires sitting on the old pins,
sort both the old pins (top to bottom) and the new pins (top to bottom), then
assign old[i] -> new[i].  Any new pin left over becomes a free input.

Usage: extend_gate.py <in.circ> <out.circ> <circuit> <gateX> <gateY> <newInputs>
"""
import re
import sys


def pin_offsets(n):
    """Relative y offsets of the input pins, top to bottom."""
    if n % 2 == 0:
        half = n // 2
        return [-10 * k for k in range(half, 0, -1)] + [10 * k for k in range(1, half + 1)]
    half = (n - 1) // 2
    return ([-10 * k for k in range(half, 0, -1)] + [0]
            + [10 * k for k in range(1, half + 1)])


WIRE_RE = re.compile(r'<wire from="\((\d+),(\d+)\)" to="\((\d+),(\d+)\)"\s*/>')
GATE_RE = r'<comp lib="\d+" loc="\(%d,%d\)" name="(?:AND|OR) Gate">'


def main():
    if len(sys.argv) < 7:
        print(__doc__)
        sys.exit(2)
    src, dst, cname = sys.argv[1], sys.argv[2], sys.argv[3]
    gx, gy, newn = int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])

    text = open(src, encoding="utf-8").read()

    m = re.search(r'<circuit name="' + re.escape(cname) + r'">', text)
    if not m:
        print("circuit not found: " + cname)
        sys.exit(1)
    start, end = m.end(), text.find("</circuit>", m.end())
    body = text[start:end]

    gm = re.search(GATE_RE % (gx, gy), body)
    if not gm:
        print(f"gate at ({gx},{gy}) not found in {cname}")
        sys.exit(1)
    gstart = gm.start()
    gend = body.find("</comp>", gstart) + len("</comp>")
    gate = body[gstart:gend]

    im = re.search(r'<a name="inputs" val="(\d+)"/>', gate)
    if not im:
        print("gate has no inputs attribute")
        sys.exit(1)
    oldn = int(im.group(1))
    if newn == oldn:
        print("input count unchanged; nothing to do")
        sys.exit(0)
    if newn < oldn:
        print(f"WARNING: shrinking {oldn} -> {newn} would orphan {oldn - newn} wire(s)")

    px = gx - 30
    old_pins = [gy + o for o in pin_offsets(oldn)]
    new_pins = [gy + o for o in pin_offsets(newn)]

    # Collect which old pin each wire endpoint sits on.
    # attached[old_pin_y] = list of (wire_match_span, which_end)
    attached = {}
    for wm in WIRE_RE.finditer(body):
        fx, fy, tx, ty = (int(g) for g in wm.groups())
        for (x, y, is_from) in ((fx, fy, True), (tx, ty, False)):
            if x == px and y in old_pins:
                attached.setdefault(y, []).append((wm.start(), wm.end(), is_from, fx, fy, tx, ty))

    print(f"gate @({gx},{gy}): inputs {oldn} -> {newn}")
    print(f"  old pins: {old_pins}")
    print(f"  new pins: {new_pins}")
    print(f"  wires attached to pins: {sum(len(v) for v in attached.values())}"
          f" over {len(attached)} pin(s)")

    # Map old pin -> new pin, preserving top-to-bottom order but assigning each
    # old pin to the *next still-free* new pin.  Index-wise correspondence is
    # wrong: with an inserted pin the shift is not uniform, and two old pins can
    # end up mapped onto the same new pin (which makes Logisim's WireRepair blow
    # up on the duplicate).
    mapping = {}
    used = set()
    newit = iter(new_pins)
    for op in old_pins:
        for np in newit:
            if np not in used:
                mapping[op] = np
                used.add(np)
                break
    print(f"  mapping: " + ", ".join(f"{a}->{b}" for a, b in mapping.items()))

    # Rewrite the wire endpoints.  Work on the body text via a single pass.
    replacements = []  # (span_start, span_end, new_text)
    for wm in WIRE_RE.finditer(body):
        fx, fy, tx, ty = (int(g) for g in wm.groups())
        nfx, nfy, ntx, nty = fx, fy, tx, ty
        if fx == px and fy in mapping:
            nfy = mapping[fy]
        if tx == px and ty in mapping:
            nty = mapping[ty]
        if (nfx, nfy) != (fx, fy) or (ntx, nty) != (tx, ty):
            replacements.append((wm.start(), wm.end(),
                                 f'<wire from="({nfx},{nfy})" to="({ntx},{nty})"/>'))

    for s, e, new in reversed(replacements):
        body = body[:s] + new + body[e:]
    print(f"  rewrote {len(replacements)} wire(s)")

    # Update the gate: input count + negate attributes.
    newgate = re.sub(r'(<a name="inputs" val=")\d+("/>)',
                     lambda mm: mm.group(1) + str(newn) + mm.group(2), gate)
    newgate = re.sub(r'\s*<a name="negate\d+" val="(?:true|false)"/>', "", newgate)
    negs = "\n".join(f'      <a name="negate{k}" val="false"/>' for k in range(newn))
    newgate = newgate.replace("</comp>", negs + "\n    </comp>")

    body = body[:gstart] + newgate + body[gend:]
    outtext = text[:start] + body + text[end:]
    open(dst, "w", encoding="utf-8", newline="").write(outtext)
    print(f"wrote {dst}")

    free = [p for p in new_pins if p not in mapping.values()]
    print(f"  free input pin(s) after extension: {free}")


if __name__ == "__main__":
    main()
