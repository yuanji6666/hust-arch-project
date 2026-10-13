import com.cburch.logisim.circuit.Circuit;
import com.cburch.logisim.comp.Component;
import com.cburch.logisim.data.Attribute;
import com.cburch.logisim.data.AttributeSet;
import com.cburch.logisim.file.Loader;
import com.cburch.logisim.file.LogisimFile;

import java.io.File;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;

/**
 * Load a test program into a circuit's instruction ROM and save a copy.
 *
 * The ROM's "contents" attribute is a package-private MemContents object, so it
 * is written through reflection.  The result is a normal .circ that Logisim can
 * run head-less with "-tty table", which makes automated verification possible.
 *
 * Usage: RomLoad <in.circ> <circuitName> <hexFile> <out.circ>
 *   hexFile: lines of hex words, optionally with a leading "v2.0 raw"
 */
public class RomLoad {

    static Object getAttr(Component c, String name) {
        AttributeSet as = c.getAttributeSet();
        for (Attribute<?> a : as.getAttributes()) {
            if (a.getName().equals(name)) return as.getValue(a);
        }
        return null;
    }

    public static void main(String[] args) throws Exception {
        if (args.length < 4) {
            System.err.println("usage: RomLoad <in.circ> <circuitName> <hexFile> <out.circ>");
            System.exit(2);
        }
        File in = new File(args[0]);
        String cname = args[1];
        String hexPath = args[2];
        File out = new File(args[3]);

        List<Integer> words = new ArrayList<>();
        for (String line : Files.readAllLines(Paths.get(hexPath))) {
            String t = line.trim();
            if (t.isEmpty() || t.startsWith("v2.0") || t.startsWith("#")) continue;
            // a line may hold several space-separated words
            for (String tok : t.split("\\s+")) {
                if (tok.isEmpty()) continue;
                words.add((int) Long.parseLong(tok, 16));
            }
        }
        System.out.println("program words: " + words.size());

        Loader loader = new Loader(null);
        // Logisim resolves "jar#cs3410.jar#..." relative to its current
        // directory; if that fails it tries to pop a file chooser.  Point the
        // JVM's working directory at the circuit's own folder (which holds both
        // jars) so resolution always succeeds and no dialog is ever attempted.
        if (in.getAbsoluteFile().getParentFile() != null) {
            System.setProperty("user.dir", in.getAbsoluteFile().getParentFile().getAbsolutePath());
        }
        LogisimFile lf = LogisimFile.load(in, loader);

        Circuit target = null;
        for (Circuit c : lf.getCircuits()) {
            if (c.getName().equals(cname)) { target = c; break; }
        }
        if (target == null) {
            System.err.println("no circuit named " + cname);
            for (Circuit c : lf.getCircuits()) System.err.println("   " + c.getName());
            System.exit(1);
        }

        Component rom = null;
        for (Component comp : target.getNonWires()) {
            if (comp.getFactory().getName().equals("ROM")) { rom = comp; break; }
        }
        if (rom == null) {
            System.err.println("no ROM in " + cname);
            System.exit(1);
        }

        Object mc = getAttr(rom, "contents");
        if (mc == null) {
            System.err.println("ROM has null contents");
            System.exit(1);
        }
        Class<?> k = mc.getClass();
        Method clear = k.getMethod("clear");
        Method set = k.getMethod("set", long.class, int.class);
        clear.setAccessible(true);
        set.setAccessible(true);
        clear.invoke(mc);
        for (int i = 0; i < words.size(); i++) {
            set.invoke(mc, (long) i, words.get(i));
        }
        Method get = k.getMethod("get", long.class);
        get.setAccessible(true);
        int nz = 0;
        for (int i = 0; i < words.size(); i++) {
            if ((Integer) get.invoke(mc, (long) i) != 0) nz++;
        }
        System.out.println("ROM now holds " + nz + " non-zero words at offsets 0.." + (words.size() - 1));

        if (!loader.save(lf, out)) {
            System.err.println("save failed");
            System.exit(1);
        }
        System.out.println("wrote " + out);
    }
}
