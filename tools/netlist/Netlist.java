import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.Wire;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;

import java.io.File;
import java.util.*;

/**
 * Exact netlist extractor for Logisim .circ files.
 *
 * Uses Logisim's own getEnds() for precise pin locations and Wire endpoints for
 * connectivity, then resolves every net by union-find. No geometric guessing.
 *
 * Usage: java Netlist <file.circ> <circuitName> [signalName]
 */
public class Netlist {

    /** A pin: which component, which end index, input or output. */
    static class Pin {
        final Component comp;
        final int idx;
        final Location loc;
        final boolean input, output;
        Pin(Component c, int i, Location l, boolean in, boolean out) {
            comp = c; idx = i; loc = l; input = in; output = out;
        }
    }

    static final Map<Location, Integer> ids = new HashMap<>();
    static int[] parent = new int[64];

    static int id(Location l) {
        Integer v = ids.get(l);
        if (v == null) {
            v = ids.size();
            ids.put(l, v);
            if (v >= parent.length) {
                int[] np = new int[Math.max(parent.length * 2, v + 1)];
                System.arraycopy(parent, 0, np, 0, parent.length);
                for (int i = parent.length; i < np.length; i++) np[i] = i;
                parent = np;
            }
        }
        return v;
    }

    static int find(int a) {
        while (parent[a] != a) { parent[a] = parent[parent[a]]; a = parent[a]; }
        return a;
    }

    static void union(int a, int b) {
        int ra = find(a), rb = find(b);
        if (ra != rb) parent[ra] = rb;
    }

    static String label(Component c) {
        AttributeSetLike as = new AttributeSetLike(c);
        String s = as.get("label");
        if (s == null || s.isEmpty()) s = as.get("text");
        return s == null ? "" : s;
    }

    /**
     * Logisim's Pin reports isOutput() for both directions, so the real
     * direction must come from the "output" attribute ("true" = output pin).
     */
    static boolean isOutputPin(Component c) {
        String o = new AttributeSetLike(c).get("output");
        return "true".equalsIgnoreCase(o);
    }

    /** Tiny wrapper to read attributes without importing AttributeSet directly. */
    static class AttributeSetLike {
        final Component c;
        AttributeSetLike(Component c) { this.c = c; }
        String get(String name) {
            try {
                com.cburch.logisim.data.AttributeSet as = c.getAttributeSet();
                for (Attribute<?> a : as.getAttributes()) {
                    if (a.getName().equals(name)) {
                        Object v = as.getValue(a);
                        return v == null ? null : v.toString();
                    }
                }
            } catch (Throwable t) { /* ignore */ }
            return null;
        }
    }

    static String pos(Component c) {
        Location l = c.getLocation();
        return "(" + l.getX() + "," + l.getY() + ")";
    }

    static boolean isGate(String n, String kind) { return kind.equals(n); }

    /** Recursively build the boolean expression driving the net at loc. */
    static String expr(Location loc, List<Pin> pins, Map<Integer, List<Pin>> byNet,
                       Set<Integer> guard, int depth) {
        if (depth > 24) return "?";
        int net = find(id(loc));
        if (guard.contains(net)) return "?";
        guard.add(net);
        try {
            List<Pin> on = byNet.get(net);
            if (on == null) return "?";
            // an input Pin sitting on this net names the literal
            for (Pin p : on) {
                if (p.comp.getFactory().getName().equals("Pin") && !isOutputPin(p.comp)) {
                    String l = label(p.comp);
                    if (l != null && !l.isEmpty()) return l;
                }
            }
            for (Pin p : on) {
                String n = p.comp.getFactory().getName();
                if (!p.output) continue;
                if (n.equals("Pin")) continue; // not a logic source
                if (n.equals("NOT Gate")) {
                    Location in = inputLoc(p, pins);
                    return "~" + expr(in, pins, byNet, guard, depth + 1);
                }
                if (n.equals("AND Gate")) {
                    return andTerms(p, pins, byNet, guard, depth);
                }
                if (n.equals("OR Gate")) {
                    List<String> parts = new ArrayList<>();
                    for (Location in : inputLocs(p, pins)) {
                        parts.add(expr(in, pins, byNet, guard, depth + 1));
                    }
                    return "(" + String.join(" | ", parts) + ")";
                }
                if (n.equals("Controlled Buffer") || n.equals("Bit Extender")) {
                    Location in = inputLoc(p, pins);
                    if (in != null) return expr(in, pins, byNet, guard, depth + 1);
                }
            }
            return "?";
        } finally {
            guard.remove(net);
        }
    }

    /**
     * Map from a coordinate to the name of the input Pin sitting exactly there.
     * NOT gates read literals straight off the input pins, so the literal name
     * must be recovered by coordinate lookup rather than by tracing wires.
     */
    static Map<Location, String> literalAt = new HashMap<>();

    static String literalName(Location l) {
        String s = literalAt.get(l);
        return s == null ? "?" : s;
    }

    static String andTerms(Pin gate, List<Pin> pins, Map<Integer, List<Pin>> byNet,
                           Set<Integer> guard, int depth) {
        List<String> terms = new ArrayList<>();
        for (Location in : inputLocs(gate, pins)) {
            terms.add(termOf(in, pins, byNet, guard, depth));
        }
        return String.join(" & ", terms);
    }

    /** One AND input: either a literal pin, or an inverted literal. */
    static String termOf(Location in, List<Pin> pins, Map<Integer, List<Pin>> byNet,
                         Set<Integer> guard, int depth) {
        if (literalAt.containsKey(in)) return literalAt.get(in);
        // look for a NOT gate whose output is on this net
        int net = find(id(in));
        List<Pin> on = byNet.get(net);
        if (on != null) {
            for (Pin p : on) {
                if (!p.output) continue;
                if (p.comp.getFactory().getName().equals("NOT Gate")) {
                    Location src = inputLoc(p, pins);
                    if (src != null && literalAt.containsKey(src)) {
                        return "~" + literalAt.get(src);
                    }
                }
                if (p.comp.getFactory().getName().equals("Pin")) {
                    String l = label(p.comp);
                    if (l != null && !l.isEmpty()) return l;
                }
            }
        }
        return "?";
    }

    static List<Location> inputLocs(Pin gate, List<Pin> pins) {
        List<Location> res = new ArrayList<>();
        for (EndData ed : gate.comp.getEnds()) {
            if (ed.isInput()) res.add(ed.getLocation());
        }
        return res;
    }

    static Location inputLoc(Pin gate, List<Pin> pins) {
        List<Location> l = inputLocs(gate, pins);
        return l.isEmpty() ? null : l.get(0);
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("usage: Netlist <file.circ> <circuitName> [signalFilter]");
            System.exit(2);
        }
        File circ = new File(args[0]);
        String want = args[1];
        String filter = args.length > 2 ? args[2] : null;

        // Libraries referenced by the .circ (cs3410.jar, riscv-probe.jar) are
        // resolved by Logisim relative to the file, so they must sit beside it.
        Loader loader = new Loader(null);
        LogisimFile lf = LogisimFile.load(circ, loader);

        Circuit target = null;
        for (Circuit c : lf.getCircuits()) {
            if (c.getName().equals(want)) { target = c; break; }
        }
        if (target == null) {
            System.err.println("circuit not found: " + want);
            System.err.println("available:");
            for (Circuit c : lf.getCircuits()) System.err.println("   " + c.getName());
            System.exit(1);
        }

        // gather pins
        List<Pin> pins = new ArrayList<>();
        literalAt.clear();
        for (Component c : target.getNonWires()) {
            boolean outPin = isOutputPin(c);
            for (EndData ed : c.getEnds()) {
                pins.add(new Pin(c, -1, ed.getLocation(), ed.isInput(), ed.isOutput()));
                // record input-pin coordinates so literals can be named
                if (c.getFactory().getName().equals("Pin") && !outPin && ed.isInput()) {
                    String l = label(c);
                    if (l != null && !l.isEmpty()) literalAt.put(ed.getLocation(), l);
                }
            }
        }
        // ensure every pin location has an id
        for (Pin p : pins) id(p.loc);
        for (int i = 0; i < parent.length; i++) parent[i] = i;
        for (int i = 0; i < ids.size(); i++) parent[i] = i;

        // wires join their endpoints
        for (Wire w : target.getWires()) {
            int a = id(w.getEnd0()), b = id(w.getEnd1());
            union(a, b);
        }
        // a pin at the same location as a wire endpoint is on that net automatically (same Location id)

        Map<Integer, List<Pin>> byNet = new HashMap<>();
        for (Pin p : pins) byNet.computeIfAbsent(find(id(p.loc)), k -> new ArrayList<>()).add(p);

        System.out.println("# circuit: " + want);
        System.out.println("# components: " + target.getNonWires().size()
                + "  wires: " + target.getWires().size()
                + "  pins: " + pins.size()
                + "  nets: " + byNet.size());
        System.out.println();

        // debug: inspect Pin components' attributes and end types
        if ("@pins".equals(filter)) {
            for (Component c : target.getNonWires()) {
                if (!c.getFactory().getName().equals("Pin")) continue;
                StringBuilder at = new StringBuilder();
                try {
                    com.cburch.logisim.data.AttributeSet as = c.getAttributeSet();
                    for (Attribute<?> a : as.getAttributes()) {
                        try {
                            at.append(a.getName()).append("=").append(as.getValue(a)).append(" ");
                        } catch (Throwable t) { at.append(a.getName()).append("=<err> "); }
                    }
                } catch (Throwable t) { at.append("<no attrset> "); }
                StringBuilder ed = new StringBuilder();
                for (EndData e : c.getEnds()) {
                    ed.append("[").append(e.getLocation())
                      .append(" in=").append(e.isInput())
                      .append(" out=").append(e.isOutput()).append("]");
                }
                System.out.println(String.format("%-12s %-14s attrs: %s ends: %s",
                        pos(c), label(c), at.toString().trim(), ed.toString()));
            }
            return;
        }

        // debug: dump the literal map (input Pin -> coordinate)
        if ("@literals".equals(filter)) {
            List<String> ls = new ArrayList<>();
            for (Map.Entry<Location, String> e : literalAt.entrySet()) {
                ls.add(String.format("%-6s %s", e.getValue(),
                        "(" + e.getKey().getX() + "," + e.getKey().getY() + ")"));
            }
            Collections.sort(ls);
            for (String s : ls) System.out.println(s);
            System.out.println("# total literals: " + ls.size());
            return;
        }

        // debug: list every end of every component (full pin map)
        if ("@ends".equals(filter)) {
            for (Component c : target.getNonWires()) {
                String n = c.getFactory().getName();
                if (n.equals("Wire")) continue;
                StringBuilder sb = new StringBuilder();
                for (EndData ed : c.getEnds()) {
                    sb.append(" [").append(ed.getLocation())
                      .append(ed.isInput() ? "I" : "").append(ed.isOutput() ? "O" : "")
                      .append("]");
                }
                System.out.println(String.format("%-16s %-12s %s%s", n, pos(c), label(c), sb));
            }
            return;
        }

        // debug: dump every end of every component at a given coordinate
        if (filter != null && filter.startsWith("@")) {
            String[] xy = filter.substring(1).split(",");
            int qx = Integer.parseInt(xy[0].trim()), qy = Integer.parseInt(xy[1].trim());
            Location q = Location.create(qx, qy);
            System.out.println("### net at (" + qx + "," + qy + ")  id=" + id(q) + " root=" + find(id(q)));
            for (Component c : target.getNonWires()) {
                for (EndData ed : c.getEnds()) {
                    if (ed.getLocation().equals(q)) {
                        System.out.println("   end  " + c.getFactory().getName()
                                + " @" + pos(c) + "  in=" + ed.isInput() + " out=" + ed.isOutput()
                                + " label=" + label(c));
                    }
                }
            }
            for (Wire w : target.getWires()) {
                if (w.contains(q)) {
                    System.out.println("   wire " + w.getEnd0() + " -> " + w.getEnd1());
                }
            }
            System.out.println("### all ends sharing this net:");
            for (Component c : target.getNonWires()) {
                for (EndData ed : c.getEnds()) {
                    if (find(id(ed.getLocation())) == find(id(q))) {
                        System.out.println("   " + c.getFactory().getName() + " @" + pos(c)
                                + " end=" + ed.getLocation() + " in=" + ed.isInput()
                                + " out=" + ed.isOutput() + " label=" + label(c));
                    }
                }
            }
            return;
        }

        // report every output Pin's expression
        List<String> lines = new ArrayList<>();
        for (Pin p : pins) {
            String n = p.comp.getFactory().getName();
            if (!n.equals("Pin") || !isOutputPin(p.comp)) continue;
            String sig = label(p.comp);
            if (filter != null && !filter.equals(sig)) continue;
            // expression is driven by whatever feeds this net (excluding this pin's own output)
            int net = find(id(p.loc));
            String e = exprFromNet(net, pins, byNet);
            lines.add(String.format("%-12s = %s", sig, e));
        }
        Collections.sort(lines);
        for (String s : lines) System.out.println(s);
    }

    static String exprFromNet(int net, List<Pin> pins, Map<Integer, List<Pin>> byNet) {
        List<Pin> on = byNet.get(net);
        if (on == null) return "?";
        // a directly-wired literal (single-minterm signals bypass the OR gate)
        for (Pin p : on) {
            if (p.comp.getFactory().getName().equals("Pin") && !isOutputPin(p.comp)) {
                String l = label(p.comp);
                if (l != null && !l.isEmpty()) return l;
            }
        }
        for (Pin p : on) {
            String n = p.comp.getFactory().getName();
            if (!p.output) continue;
            if (n.equals("Pin")) continue; // skip Pin components entirely
            if (n.equals("OR Gate")) {
                List<String> parts = new ArrayList<>();
                for (EndData ed : p.comp.getEnds()) {
                    if (!ed.isInput()) continue;
                    parts.add(expr(ed.getLocation(), pins, byNet, new HashSet<>(), 0));
                }
                return "(" + String.join(" | ", parts) + ")";
            }
            if (n.equals("AND Gate")) {
                return andTerms(p, pins, byNet, new HashSet<>(), 0);
            }
            if (n.equals("NOT Gate")) {
                Location in = inputLoc(p, pins);
                return "~" + expr(in, pins, byNet, new HashSet<>(), 0);
            }
        }
        return "?";
    }
}

