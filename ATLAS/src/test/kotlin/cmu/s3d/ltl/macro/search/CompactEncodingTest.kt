package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.*
import cmu.s3d.ltl.learning.AlloyMaxBase
import cmu.s3d.ltl.macro.constraint.ProductConstraintAutomaton
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.UFreeLassoOracle
import cmu.s3d.ltl.samples2ltl.TaskParser
import edu.mit.csail.sdg.alloy4.A4Reporter
import edu.mit.csail.sdg.parser.CompUtil
import edu.mit.csail.sdg.translator.*
import java.io.File
import org.junit.jupiter.api.Test
import kotlin.test.*

class CompactEncodingTest {
    @Test fun largeFiberDomainsAreQuotientedAndParseWithoutStackOverflow() {
        val task = TaskParser.parseTask(File("benchmark/increasingNumVariables/0053.trace").readText())
        val matched = task.copy(excludedOperators = (task.excludedOperators + "Until").distinct())
        val plan = (RecognizedConstraintAnalyzer.analyze(matched,2) as MacroTaskAnalysis.Supported).plan
        fun <Q:Any> check(p: MacroConstraintPlan<Q>) {
            val context = MacroCompilationContext(p,matched.positiveExamples,matched.negativeExamples)
            assertEquals(2634,context.catalog.unquotientedSize)
            assertTrue(context.catalog.entries.size < context.catalog.unquotientedSize / 2,
                "quotient retained ${context.catalog.entries.size}/${context.catalog.unquotientedSize}")
            val source = MacroAlloyModelBuilder(context).build()
            CompUtil.parseEverything_fromString(A4Reporter.NOP,source)
        }
        check(plan)
    }

    @Test fun repeatedTraceShapesDoNotReplicateTemporalClausesOrPositionAtoms() {
        val task = TaskParser.parseTask(File("benchmark/5to10Traces/0075.trace").readText())
        val uFree = task.copy(excludedOperators = (task.excludedOperators + "Until").distinct())
        val analysis = RecognizedConstraintAnalyzer.analyze(uFree,2) as MacroTaskAnalysis.Supported
        fun <Q:Any> check(plan: MacroConstraintPlan<Q>) {
            val context = MacroCompilationContext(plan,task.positiveExamples,task.negativeExamples)
            val builder = MacroAlloyModelBuilder(context)
            val source = builder.build()
            assertEquals(1220,(context.originalPositives+context.originalNegatives).sumOf { it.length() })
            assertEquals(1202,builder.positionCount)
            assertEquals(10,builder.localPositionCount)
            // This actual OOM input previously emitted 126,666,739 bytes.
            assertTrue(source.toByteArray().size < 1_000_000, "Model regression: ${source.length} bytes")
            assertEquals(builder.traceShapes.size,Regex("pred semantics").findAll(source).count())
            CompUtil.parseEverything_fromString(A4Reporter.NOP,source)
            File("target/compact-encoding-size.txt").writeText("task=5to10Traces/0075.trace\nbytes=${source.toByteArray().size}\npositionAtoms=${builder.localPositionCount}\ninputLogicalPositions=1220\nencodedLogicalPositions=${builder.positionCount}\n")
        }
        check(analysis.plan)
    }

    @Test fun sharedPredicatesAndEveryPositionAgreeWithIndependentWordOracle() {
        val plan = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),5,0)
        fun trace(bits: List<Boolean>, loop: Int): LassoTrace {
            val states = bits.map { State(mapOf("p" to it)) }
            return LassoTrace(states.take(loop),states.drop(loop))
        }
        // Different valuations of the same shape, different loop starts, and unequal lengths.
        val traces = listOf(trace(listOf(true,false,false),1),trace(listOf(false,true,true),1),
            trace(listOf(false,false,true),0),trace(listOf(true,false,true,false,true),3),trace(listOf(false),0))
        val registry = ConstraintStateRegistry(plan)
        val entries = FiberCatalog(registry).entries.filter { it.length < plan.nodeBudget && it.key.semanticType.xCount <= 2 }
            .distinctBy { it.key.semanticType }
        val options = AlloyMaxBase.defaultAlloyOptions().apply { solver = A4Options.SatSolver.SAT4JMax }
        var comparisons = 0
        for (entry in entries) {
            var root = NodeId("p")
            val nodes = arrayListOf<FormulaNode>(LiteralNode(root,"p"))
            for ((i,op) in entry.word.operators.asReversed().withIndex()) {
                val id = NodeId("u$i"); nodes.add(UnaryNode(id,op,root)); root=id
            }
            val dag = FormulaDag(root,nodes)
            val (positive,negative) = traces.partition { UFreeLassoOracle.evaluate(dag,it)[0] }
            val context = MacroCompilationContext(plan,positive,negative)
            val selected = context.catalog.entries.single { candidate ->
                candidate.qIn == entry.qIn && candidate.qOut == entry.qOut &&
                    candidate.key.nonEmpty == entry.key.nonEmpty && context.positions.all { positions ->
                        positions.semanticFunctionKey(candidate.key.semanticType) == positions.semanticFunctionKey(entry.key.semanticType)
                    }
            }
            val source = MacroAlloyModelBuilder(context).build() + "\nfact { active = A0 and A0.lab = T0 and R.fiber = E${selected.id} }\n"
            val world = CompUtil.parseEverything_fromString(A4Reporter.NOP,source)
            val solution = TranslateAlloyToKodkod.execute_command(A4Reporter.NOP,world.allReachableSigs,world.allCommands.first(),options)
            assertTrue(solution.satisfiable(),entry.word.toString())
            for ((i,positions) in context.positions.withIndex()) {
                val expected = UFreeLassoOracle.evaluate(dag,positions.trace)
                for (at in expected.indices) {
                    val actual = solution.eval(CompUtil.parseOneExpression_fromString(world,"R->P$at in ev$i")) as Boolean
                    assertEquals(expected[at],actual,"word=${entry.word}, trace=$i position=$at")
                    comparisons++
                }
            }
        }
        assertTrue(entries.size >= 20)
        File("target/compact-encoding-semantics.txt").writeText("fibers=${entries.size}\npositionComparisons=$comparisons\nmismatches=0\n")
    }
}
