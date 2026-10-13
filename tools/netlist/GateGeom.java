import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.comp.ComponentFactory;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.data.Bounds;
import com.cburch.logisim.data.Location;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;
import com.cburch.logisim.tools.Library;
import com.cburch.logisim.tools.AddTool;
import com.cburch.logisim.tools.Tool;

import java.util.List;

/**
 * Ask Logisim itself for the exact pin geometry of AND / OR gates at every
 * input count, by instantiating each gate on a scratch circuit.
 *
 * Usage: GateGeom
 */
public class GateGeom {

    public static void main(String[] args) throws Exception {
        Loader loader = new Loader(null);
        // load an existing project so its libraries (including the built-in
        // wiring/gates library) are populated
        String circPath = args.length > 0 ? args[0] : "circuits/cpu21-riscv -单周期24+4ccab指令(me).circ";
        java.io.File in = new java.io.File(circPath);
        if (in.getAbsoluteFile().getParentFile() != null) {
            System.setProperty("user.dir", in.getAbsoluteFile().getParentFile().getAbsolutePath());
        }
        LogisimFile lf = LogisimFile.load(in, loader);

        for (String gateName : new String[]{"AND Gate", "OR Gate"}) {
            ComponentFactory factory = null;
            for (Library lib : lf.getLibraries()) {
                for (Tool t : lib.getTools()) {
                    if (t instanceof AddTool && t.getName().equals(gateName)) {
                        factory = ((AddTool) t).getFactory();
                    }
                }
            }
            if (factory == null) {
                System.out.println(gateName + ": factory not found (libs=" + lf.getLibraries().size() + ")");
                continue;
            }
            System.out.println("##### " + gateName);
            for (int n = 2; n <= 14; n++) {
                try {
                    AttributeSet attrs = factory.createAttributeSet();
                    for (Attribute<?> a : attrs.getAttributes()) {
                        if (a.getName().equals("inputs")) {
                            @SuppressWarnings("unchecked")
                            Attribute<Integer> ai = (Attribute<Integer>) a;
                            attrs.setValue(ai, n);
                        }
                    }
                    Component c = factory.createComponent(Location.create(1000, 5000), attrs);
                    Bounds b = c.getBounds();
                    StringBuilder sb = new StringBuilder();
                    for (com.cburch.logisim.comp.EndData e : c.getEnds()) {
                        Location l = e.getLocation();
                        sb.append(String.format("%s%s%d ", e.isInput() ? "in" : "out",
                                l.getY() >= 5000 ? "+" : "-",
                                Math.abs(l.getY() - 5000)));
                    }
                    System.out.printf("  inputs=%-2d  bounds w=%d h=%d  %s%n",
                            n, b.getWidth(), b.getHeight(), sb);
                } catch (Throwable t) {
                    System.out.println("  inputs=" + n + " -> " + t);
                }
            }
            System.out.println();
        }
    }
}
