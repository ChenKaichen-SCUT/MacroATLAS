package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.macro.constraint.ProductConstraintAutomaton
import org.junit.jupiter.api.Test
import java.io.File
import java.util.concurrent.TimeUnit
import kotlin.test.*

class AutoDomainSafetyTest {
    @Test fun consequentTemplateNeedsThreeBinaryNodes() {
        fun supported(b:Int) = MacroTaskAnalysis.Supported(
            MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("x0"),18,b),
            listOf("OfficialWeakeningConsequent"))
        assertEquals(AutoDomainSafety.TEMPLATE_MINIMUM,AutoDomainSafety.precheck(supported(2)))
        assertNull(AutoDomainSafety.precheck(supported(3)))
    }

    @Test fun experimentAutoFallsBackAfterBoundedUnsat() {
        val output=File("target/auto-bounded-unsat-test").apply { deleteRecursively();mkdirs() }
        val command=listOf(File(System.getProperty("java.home"),"bin/java").path,
            "-Djava.library.path=./lib","-cp",System.getProperty("java.class.path"),
            "cmu.s3d.ltl.experiment.ExperimentMain",
            "--mode","auto","--file","src/test/resources/macro/next.trace",
            "--b","0","--B","1","--output",output.path)
        val process=ProcessBuilder(command).redirectErrorStream(true).start()
        val log=StringBuilder()
        val reader=Thread { process.inputStream.bufferedReader().use { log.append(it.readText()) } }.apply { start() }
        if(!process.waitFor(60,TimeUnit.SECONDS)) {
            process.destroyForcibly();reader.join();fail("Experiment AUTO timed out")
        }
        reader.join()
        assertEquals(0,process.exitValue(),log.toString())
        val metadata=output.resolve("metadata.json").readText()
        assertTrue(metadata.contains("\"status\":\"FALLBACK\""),metadata)
        assertTrue(metadata.contains("\"solverMode\":\"ORIGINAL\""),metadata)
        assertTrue(metadata.contains("\"fallbackReason\":\"BOUNDED_MACRO_UNSAT\""),metadata)
        assertTrue(output.resolve("bounded-attempt.json").isFile)
        assertEquals("X(x0)",output.resolve("reconstructed_formula.txt").readText().trim())
    }
}
