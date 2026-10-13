#!/usr/bin/env python3
"""
Extend an AND/OR gate's input count inside a Logisim .circ and remap every wire
that was attached to its input pins.

!! NOT WORKING -- DO NOT USE !!
   The remap below edits wire endpoints in place and can leave two wires on the
   same pin while another pin is orphaned, which produces a circuit Logisim
   cannot load (it runs out of heap).  The correct approach is to collect the
   attached wires, then rewrite their pin endpoints in order, assigning the
   sorted old pins to the sorted new pin positions.

   Gate geometry itself IS verified -- see tools/netlist/GateGeom.java.

Logisim's gate pin geometry (verified against Logisim's own createComponent):

    even n : inputs at  y-k*10 for k = n/2 .. 1, then y+k*10 for k = 1 .. n/2
             (no pin at y+0)
    odd  n : inputs at  y-k*10 for k = (n-1)/2 .. 1, then y+0,
             then y+k*10 for k = 1 .. (n-1)/2

So changing n shifts the existing pins, and all wires must be remapped.

Usage: extend_gate.py <in.circ> <out.circ> <circuit> <gateX> <gateY> <newInputs>
"""
import re
import sys
import xml.etree.ElementTree as ET


def pin_offsets(n):
    """Relative y offsets of the input pins, top to bottom."""
    if n % 2 == 0:
        half = n // 2
        return [-10 * k for k in range(half, 0, -1)] + [10 * k for k in range(1, half + 1)]
    half = (n - 1) // 2
    return ([-10 * k for k in range(half, 0, -1)] + [0]
            + [10 * k for k in range(1, half + 1)])


def main():
    src, dst, cname, gx, gy, newn = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
    text = open(src, encoding="utf-8").read()

    m = re.search(r'<circuit name="' + re.escape(cname) + r'">', text)
    if not m:
        print("circuit not found")
        sys.exit(1)
    start = m.end()
    end = text.find("</circuit>", start)
    body = text[start:end]

    # locate the gate
    gm = re.search(r'<comp lib="\d+" loc="\(' + str(gx) + r',' + str(gy) + r'\)" name="(AND|OR) Gate">', body)
    if not gm:
        print(f"gate at ({gx},{gy}) not found")
        sys.exit(1)
    gstart = gm.start()
    gend = body.find("</comp>", gstart) + len("</comp>")
    gate = body[gstart:gend]

    im = re.search(r'<a name="inputs" val="(\d+)"/>', gate)
    oldn = int(im.group(1))
    print(f"gate {gm.group(1)} @({gx},{gy}): inputs {oldn} -> {newn}")

    old_off = pin_offsets(oldn)
    new_off = pin_offsets(newn)
    old_pin_ys = [gy + o for o in old_off]
    new_pin_ys = [gy + o for o in new_off]

    # Which wires attach to a pin?  A wire endpoint exactly on (gx-30, y).
    px = gx - 30

    def remap(match):
        f, t = match.group(1), match.group(2)
        fx, fy = map(int, re.match(r"\((\d+),(\d+)\)", f).groups())
        tx, ty = map(int, re.match(r"\((\d+),(\d+)\)", t).groups())
        for a, b in ((fx, fy), (tx, ty)):
            if a == px and b in old_pin_ys:
                idx = old_pin_ys.index(b)
                newy = new_pin_ys[idx]
                if (a, b) == (fx, fy):
                    f = f"({a},{newy})"
                else:
                    t = f"({a},{newy})"
                print(f"   remap pin y={b} -> {newy}")
        return f'<wire from="{f}" to="{t}"/>'

    newbody, n = re.subn(r'<wire from="(\(\d+,\d+\))" to="(\(\d+,\d+\))"\s*/>', remap, body)

    # update the gate's input count and negate attributes
    newgate = re.sub(r'(<a name="inputs" val=")\d+("/>)', lambda mm: mm.group(1) + str(newn) + mm.group(2), gate)
    # drop old negateK, then re-add exactly newn of them
    newgate = re.sub(r'\s*<a name="negate\d+" val="(?:true|false)"/>', "", newgate)
    negs = "\n".join(f'      <a name="negate{k}" val="false"/>' for k in range(newn))
    newgate = newgate.replace("</comp>", negs + "\n    </comp>")

    outtext = text[:start] + newbody.replace(gate, newgate) + text[end:]
    open(dst, "w", encoding="utf-8", newline="").write(outtext)
    print(f"wrote {dst}")
    print(f"  new pin ys: {new_pin_ys}")


if __name__ == "__main__":
    main()
