import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.circuit.CircuitState;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.EndData;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.data.Value;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.proj.Project;

import java.io.File;
import java.lang.reflect.Method;
import java.util.*;

/**
 * Single-step the circuit and dump the register file after each clock.
 *
 * Usage: StepDump <file.circ> <circuitName> <steps>
 */
public class StepDump {

    static Object attr(Component c, String n) {
        AttributeSet as = c.getAttributeSet();
        for (Attribute<?> a : as.getAttributes()) {
            if (a.getName().equals(n)) return as.getValue(a);
        }
        return null;
    }

    public static void main(String[] args) throws Exception {
        File circ = new File(args[0]);
        String cname = args[1];
        int steps = args.length > 2 ? Integer.parseInt(args[2]) : 40;

        if (circ.getAbsoluteFile().getParentFile() != null) {
            System.setProperty("user.dir", circ.getAbsoluteFile().getParentFile().getAbsolutePath());
        }
        Loader loader = new Loader(null);
        LogisimFile lf = LogisimFile.load(circ, loader);
        Circuit target = null;
        for (Circuit c : lf.getCircuits()) if (c.getName().equals(cname)) target = c;

        Project proj = new Project(lf);
        CircuitState st = proj.getCircuitState(target);

        // locate the clock and the register file
        Component clk = null, regf = null;
        for (Component c : target.getNonWires()) {
            String n = c.getFactory().getName();
            if (n.equals("Clock")) clk = c;
            if (n.equals("Regifile") || n.equals("RegisterFile") || n.contains("Regifile")) regf = c;
        }
        System.out.println("clock = " + (clk == null ? "NOT FOUND" : clk.getLocation()));
        System.out.println("regfile = " + (regf == null ? "NOT FOUND" : regf.getLocation()));
        if (regf != null) {
            System.out.println("  regfile factory: " + regf.getFactory().getName());
            for (EndData e : regf.getEnds()) {
                System.out.println("    end " + e.getLocation() + " in=" + e.isInput() + " out=" + e.isOutput());
            }
        }
        if (clk == null) { System.out.println("cannot step without a clock"); return; }

        Location clkLoc = clk.getLocation();
        int clkEnd = 0;
        List<EndData> ce = clk.getEnds();
        for (int i = 0; i < ce.size(); i++) if (ce.get(i).isOutput()) clkEnd = i;

        System.out.println();
        System.out.println("step  PC        IR        reg1(s1)  reg5(t0)  reg6(t1)  reg28(t3)");
        for (int s = 0; s < steps; s++) {
            // rising edge
            st.setValue(clkLoc, Value.TRUE, clk, clkEnd);
            st.getPropagator().propagate();
            st.setValue(clkLoc, Value.FALSE, clk, clkEnd);
            st.getPropagator().propagate();
            // read some probe-able values
            System.out.printf("%4d  %s%n", s, describe(st, target));
        }
    }

    static String describe(CircuitState st, Circuit target) {
        StringBuilder sb = new StringBuilder();
        for (Component c : target.getNonWires()) {
            String n = c.getFactory().getName();
            if (!n.equals("Probe")) continue;
            String lab = (String) attr(c, "label");
            if (lab == null) lab = "";
            if (!lab.isEmpty()) {
                Value v = st.getValue(c.getLocation());
                sb.append(lab).append("=").append(v == null ? "?" : v.toHexString()).append(" ");
            }
        }
        return sb.toString();
    }
}
