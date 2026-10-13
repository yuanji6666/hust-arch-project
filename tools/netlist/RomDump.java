import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;

import java.io.File;
import java.lang.reflect.Method;

/**
 * Read (and show how to write) the instruction ROM contents.
 *
 * Usage: RomDump <file.circ> <circuitName> [--write <hex-file> <out.circ>]
 */
public class RomDump {

    static Object getAttr(Component c, String name) {
        AttributeSet as = c.getAttributeSet();
        for (Attribute<?> a : as.getAttributes()) {
            if (a.getName().equals(name)) return as.getValue(a);
        }
        return null;
    }

    public static void main(String[] args) throws Exception {
        File circ = new File(args[0]);
        String cname = args[1];
        Loader loader = new Loader(null);
        LogisimFile lf = LogisimFile.load(circ, loader);

        Circuit target = null;
        for (Circuit c : lf.getCircuits()) {
            if (c.getName().equals(cname)) { target = c; break; }
        }
        if (target == null) { System.err.println("no circuit " + cname); System.exit(1); }

        for (Component comp : target.getNonWires()) {
            if (!comp.getFactory().getName().equals("ROM")) continue;
            Object mc = getAttr(comp, "contents");
            System.out.println("ROM @" + comp.getLocation() + "  contents=" + mc);
            if (mc == null) { System.out.println("  (null)"); continue; }

            Class<?> k = mc.getClass();
            System.out.println("  class: " + k.getName());
            // MemContents is package-private, so its public methods need
            // setAccessible(true) to be usable from outside the package.
            try {
                java.lang.reflect.Method sa = java.lang.reflect.AccessibleObject.class
                        .getMethod("setAccessible", boolean.class);
                for (Method m : k.getMethods()) {
                    try { sa.invoke(m, true); } catch (Throwable ignore) {}
                }
            } catch (Throwable t) {
                System.out.println("  setAccessible unavailable: " + t);
            }
            for (String m : new String[]{"getLogLength", "getValueWidth", "getWidth",
                                         "getFirstOffset", "getLastOffset", "isClear"}) {
                try {
                    Method mm = k.getMethod(m);
                    mm.setAccessible(true);
                    System.out.println("  " + m + "() = " + mm.invoke(mc));
                } catch (Throwable t) {
                    System.out.println("  " + m + " -> " + t);
                }
            }
            try {
                Method get = k.getMethod("get", long.class);
                get.setAccessible(true);
                int nz = 0;
                StringBuilder head = new StringBuilder();
                for (long i = 0; i < 64; i++) {
                    int v = (Integer) get.invoke(mc, i);
                    if (v != 0) nz++;
                    if (i < 8) head.append(String.format("%08x ", v));
                }
                System.out.println("  first 8 words: " + head);
                System.out.println("  non-zero words in first 64: " + nz);
            } catch (Throwable t) {
                System.out.println("  get() failed: " + t);
            }
        }
    }
}
