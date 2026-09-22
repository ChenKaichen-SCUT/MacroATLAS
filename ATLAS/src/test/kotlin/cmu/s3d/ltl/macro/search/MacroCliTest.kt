package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.samples2ltl.TaskParser
import org.junit.jupiter.api.Test
import java.io.File
import java.util.concurrent.TimeUnit
import kotlin.test.*

class MacroCliTest {
    private fun cli(vararg args: String): Pair<Int,String> {
        val process = ProcessBuilder(listOf(File(System.getProperty("java.home"),"bin/java").path,
            "-Djava.library.path=./lib","-cp",System.getProperty("java.class.path"),"cmu.s3d.ltl.app.CLIKt") + args)
            .redirectErrorStream(true).start()
        // Drain concurrently; a hung process must fail this test instead of blocking the build.
        val output = StringBuilder()
        val reader = Thread { process.inputStream.bufferedReader().use { output.append(it.readText()) } }.apply { start() }
        if(!process.waitFor(60,TimeUnit.SECONDS)) { process.destroyForcibly(); reader.join(); fail("CLI timed out") }
        reader.join()
        return process.exitValue() to output.toString()
    }

    @Test fun defaultAndOffRetainOriginalCsvAndDoNotEnterMacro() {
        val file="src/test/resources/samples2ltl/example0000.trace"
        val first=cli("-f",file,"-s","OpenWBOWeighted")
        val off=cli("-f",file,"-s","OpenWBOWeighted","--macro","off","--macro-max-binary","-1")
        assertEquals(0,first.first); assertEquals(0,off.first)
        fun normalized(s:String)=s.replace(Regex(",[0-9]+\\.[0-9]+,\\\""),",<seconds>,\"")
        assertEquals(normalized(first.second),normalized(off.second))
        assertFalse(first.second.contains("solverMode"))
        assertEquals(2,first.second.trim().lines().size)
        assertTrue(first.second.endsWith("\"!(F(x0))\"\n"))
    }

    @Test fun realParserFixturesUseMacroAndWriteVerifiedArtifacts() {
        val summary=StringBuilder()
        for(name in listOf("literal","eventually","next","nnf","repair")) {
            val directory=File("target/macro-smoke/$name")
            val result=cli("-f","src/test/resources/macro/$name.trace","--macro","force","--macro-max-binary","1","--macro-debug",directory.path)
            assertEquals(0,result.first,result.second)
            assertTrue(result.second.contains("\"solverMode\":\"MACRO\""),result.second)
            assertTrue(directory.resolve("verification.json").readText().contains("PASSED"))
            val formula=directory.resolve("reconstructed_formula.txt").readText().trim()
            val expected=when(name) { "literal"->"x0"; "eventually","repair"->"F(x0)"; "next"->"X(x0)"; else->"!(x0)" }
            assertEquals(expected,formula)
            summary.append(name).append(": ").append(formula).append("; verified\n")
        }
        File("target/phase3-smoke-results.txt").writeText(summary.toString())
    }

    @Test fun autoFallbackAndForceRejectionAreDifferentFromSupportedUnsat() {
        val u="src/test/resources/samples2ltl/example0000.trace"
        val auto=cli("--_run",u,"--macro","auto","--macro-max-binary","1")
        assertEquals(0,auto.first); assertTrue(auto.second.contains("BINARY_TEMPORAL_UNTIL_REQUIRED"))
        assertTrue(auto.second.contains("\"solverMode\":\"ORIGINAL\""))
        val force=cli("-f",u,"--macro","force","--macro-max-binary","1")
        assertTrue(force.first!=0); assertFalse(force.second.contains("solverMode\":\"ORIGINAL"))
        val unknown=File("target/unknown.trace")
        unknown.writeText(File("src/test/resources/macro/literal.trace").readText()
            .replace("1::0","1;1::0").replace("0::0","0;0::0")+"---\nfact { some DAGNode }\n")
        val fallback=cli("--_run",unknown.path,"--macro","auto","--macro-max-binary","1")
        assertEquals(0,fallback.first,fallback.second); assertTrue(fallback.second.contains("UNKNOWN_CUSTOM_ALLOY_CONSTRAINT"))
        val unsat=cli("--_run","src/test/resources/macro/next.trace","--macro","auto","--macro-max-binary","0","--macro-max-nodes","1")
        assertEquals(0,unsat.first); assertTrue(unsat.second.contains("\"solverStatus\":\"UNSAT\""))
        assertFalse(unsat.second.contains("ORIGINAL"))
    }

    @Test fun dispatchNeverCatchesInternalBugsAndOffDoesNotAnalyze() {
        val supported=RecognizedConstraintAnalyzer.analyze(TaskParser.parseTask(File("src/test/resources/macro/literal.trace").readText()),0)
        var originalCalls=0
        assertEquals("original",MacroTaskDispatcher.run(MacroSolverMode.OFF,{ error("Analyzer must not run") },{ originalCalls++; "original" },{error("Macro must not run")}))
        assertFailsWith<IllegalStateException> {
            MacroTaskDispatcher.run<String>(MacroSolverMode.AUTO,{supported},{ originalCalls++; "original" },{ error("Injected decoder invariant failure") })
        }
        assertEquals(1,originalCalls)
    }
}
