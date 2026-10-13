import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.proj.Project;

import java.io.File;
import java.util.*;

/**
 * Try to drive a Logisim circuit programmatically: list every "memory-like"
 * component (ROM / RAM / ProgramROM) together with its contents attribute, and
 * report what the RiscV Probe component exposes.
 *
 * Usage: MemProbe <file.circ> [circuitName]
 */
public class MemProbe {

    static String attr(Component c, String name) {
        try {
            AttributeSet as = c.getAttributeSet();
            for (Attribute<?> a : as.getAttributes()) {
                if (a.getName().equals(name)) {
                    Object v = as.getValue(a);
                    return v == null ? null : v.toString();
                }
            }
        } catch (Throwable t) { /* ignore */ }
        return null;
    }

    public static void main(String[] args) throws Exception {
        File circ = new File(args[0]);
        String only = args.length > 1 ? args[1] : null;
        Loader loader = new Loader(null);
        LogisimFile lf = LogisimFile.load(circ, loader);
        Project proj = new Project(lf);

        for (Circuit c : lf.getCircuits()) {
            if (only != null && !c.getName().equals(only)) continue;
            System.out.println("===== " + c.getName() + " =====");
            for (Component comp : c.getNonWires()) {
                String n = comp.getFactory().getName();
                boolean interesting = n.contains("ROM") || n.contains("RAM")
                        || n.contains("Probe") || n.contains("Memory");
                if (!interesting) continue;
                StringBuilder sb = new StringBuilder();
                AttributeSet as = comp.getAttributeSet();
                for (Attribute<?> a : as.getAttributes()) {
                    String an = a.getName();
                    if (an.equals("label") || an.equals("contents")
                            || an.equals("Contents") || an.equals("value")
                            || an.equals("addrWidth") || an.equals("dataWidth")) {
                        Object v = as.getValue(a);
                        String vs = v == null ? "" : v.toString();
                        if (vs.length() > 60) vs = vs.substring(0, 60) + "...(" + vs.length() + ")";
                        sb.append(an).append("=").append(vs).append("  ");
                    }
                }
                System.out.println("  " + n + " @" + comp.getLocation() + "  " + sb);
                CircuitState st = proj.getCircuitState(c);
                System.out.println("      features:");
                for (Object key : new String[]{"circuit", "state", "poker", "tool"}) {
                    Object f = comp.getFeature(key);
                    System.out.println("        " + key + " = " + (f == null ? "null" : f.getClass().getName()));
                }
            }
            System.out.println();
        }
    }
}
