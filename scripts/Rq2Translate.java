import edu.mit.csail.sdg.alloy4.A4Reporter;
import edu.mit.csail.sdg.ast.Module;
import edu.mit.csail.sdg.parser.CompUtil;
import edu.mit.csail.sdg.translator.A4Options;
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/** Translates one frozen Alloy model to CNF and aborts in the pre-solve reporter callback. */
public final class Rq2Translate {
    private static final class StopBeforeSolve extends RuntimeException {
        private static final long serialVersionUID = 1L;
    }
    private static final class Counts extends A4Reporter {
        int primaryVars = -1;
        int vars = -1;
        int clauses = -1;
        @Override public void solve(int primary, int total, int totalClauses) {
            primaryVars = primary;
            vars = total;
            clauses = totalClauses;
            throw new StopBeforeSolve();
        }
    }
    private static boolean stopped(Throwable error) {
        for (Throwable item = error; item != null; item = item.getCause()) {
            if (item instanceof StopBeforeSolve) return true;
        }
        return false;
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Expected exactly one .als file");
        Path path = Paths.get(args[0]);
        byte[] bytes = Files.readAllBytes(path);
        Counts reporter = new Counts();
        long start = System.nanoTime();
        Module world = CompUtil.parseEverything_fromString(reporter, new String(bytes, StandardCharsets.UTF_8));
        double parseSec = (System.nanoTime() - start) / 1e9;
        A4Options options = new A4Options();
        options.solver = A4Options.SatSolver.OpenWBOWeighted;
        options.skolemDepth = 1;
        options.noOverflow = false;
        options.inferPartialInstance = true;
        try {
            TranslateAlloyToKodkod.execute_command(reporter, world.getAllReachableSigs(), world.getAllCommands().get(0), options);
            throw new IllegalStateException("CNF reporter callback was not reached");
        } catch (Throwable error) {
            if (!stopped(error)) throw error;
        }
        if (reporter.vars < 0 || reporter.clauses < 0) throw new IllegalStateException("No CNF counts");
        double totalSec = (System.nanoTime() - start) / 1e9;
        System.out.println("{\"status\":\"TRANSLATED_ONLY\",\"solverInvoked\":false,\"primaryVars\":"
                + reporter.primaryVars + ",\"vars\":" + reporter.vars + ",\"backendTotalClauses\":"
                + reporter.clauses + ",\"modelBytes\":" + bytes.length + ",\"parseSec\":"
                + parseSec + ",\"totalSec\":" + totalSec + "}");
    }
}
