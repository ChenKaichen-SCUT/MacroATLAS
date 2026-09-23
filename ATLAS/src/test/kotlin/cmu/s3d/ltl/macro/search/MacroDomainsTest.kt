package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.*
import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.fiber.FiberTable
import cmu.s3d.ltl.macro.kernel.UFreeLassoOracle
import cmu.s3d.ltl.macro.unary.*
import cmu.s3d.ltl.samples2ltl.Task
import cmu.s3d.ltl.samples2ltl.TaskParser
import java.io.File
import org.junit.jupiter.api.Test
import kotlin.test.*

class MacroDomainsTest {
    private fun task(raw: String? = null, excluded: List<String> = listOf("Until")) = Task(listOf("x0"),
        listOf(LassoTrace(loop=listOf(State(mapOf("x0" to true))))),emptyList(),excluded,4,emptyList(),raw)

    @Test fun reachableRegistryAndCatalogAreClosedDeterministicAndRetainNonemptyIdentity() {
        val product = ProductConstraintAutomaton(listOf(NnfAutomaton(),RequiredPropositionAutomaton("p")))
        val plan = MacroConstraintPlan(product,listOf("p","q"),5,2)
        val registry = ConstraintStateRegistry(plan)
        val second = ConstraintStateRegistry(plan)
        assertEquals(registry.states,second.states)
        assertEquals(registry.states.size,registry.states.distinct().size)
        for (q in registry.states.indices) {
            for (op in plan.allowedUnaryOperators) assertTrue(registry.unaryTransition(op,q) in registry.states.indices)
            for (r in registry.states.indices) for(op in plan.allowedBinaryOperators) assertTrue(registry.binaryTransition(op,q,r) in registry.states.indices)
        }
        val catalog = FiberCatalog(registry)
        assertEquals(catalog.entries,FiberCatalog(second).entries)
        val replay = FiberTable(product,emptyList(),0)
        for(e in catalog.entries) assertEquals(e.key,replay.replay(e.key.qIn,e.word))
        val free = FiberCatalog(ConstraintStateRegistry(MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),3,0)))
        assertTrue(free.entries.any { !it.key.nonEmpty && it.key.semanticType == SemanticType.IDENTITY })
        assertTrue(free.entries.any { it.key.nonEmpty && it.key.semanticType == SemanticType.IDENTITY })
        val onlyX = FiberCatalog(ConstraintStateRegistry(MacroConstraintPlan(product,listOf("p"),3,0,listOf(UnaryOperator.X),emptyList())))
        assertTrue(onlyX.entries.all { e -> e.word.all { it == UnaryOperator.X } })
    }

    @Test fun everyCatalogSemanticMatchesIndependentRepresentativeAtEveryLassoPosition() {
        val plan = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),5,0)
        val entries = FiberCatalog(ConstraintStateRegistry(plan)).entries
        var comparisons = 0
        for (length in 1..4) for(loopStart in 0 until length) for(mask in 0 until (1 shl length)) {
            val states = (0 until length).map { State(mapOf("p" to (mask and (1 shl it) != 0))) }
            val trace = LassoTrace(states.take(loopStart),states.drop(loopStart))
            val positions = LassoPositions(trace,5)
            for(e in entries) {
                val nodes = arrayListOf<FormulaNode>(LiteralNode(NodeId("p"),"p"))
                var child = NodeId("p")
                for((i,op) in e.word.operators.asReversed().withIndex()) { val id = NodeId("u$i"); nodes.add(UnaryNode(id,op,child)); child=id }
                val expected = UFreeLassoOracle.evaluate(FormulaDag(child,nodes),trace)
                assertContentEquals(expected,positions.evaluate(e.key.semanticType,BooleanArray(length) { states[it].values.getValue("p") }))
                comparisons++
            }
        }
        assertEquals(entries.size * 98,comparisons)
        java.io.File("target/phase3-semantics-results.txt").writeText("lassos=98\nfibers=${entries.size}\nall-position vector comparisons=$comparisons\nmismatches=0\n")
        val p = LassoPositions(LassoTrace(listOf(State(mapOf("p" to true))),listOf(State(mapOf("p" to false)))),6)
        assertEquals(listOf(1,1),p.succPow[6])
        assertEquals(listOf(0,1),p.future[0])
    }

    @Test fun equivalentLassoWordsAreConstrainedOnceButOriginalSamplesAreRetained() {
        fun state(value:Boolean,explicit:Boolean=true)=State(if(explicit) mapOf("p" to value) else emptyMap())
        val first=LassoTrace(prefix=listOf(state(false,false)),loop=listOf(state(true),state(false)))
        val same=LassoTrace(loop=listOf(state(false),state(true)))
        val plan=MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),5,0)
        val context=MacroCompilationContext(plan,listOf(first,same),emptyList())
        assertEquals(2,context.originalPositives.size)
        assertEquals(1,context.positives.size)
        assertEquals(2,context.positions.single().successor.size)
    }

    @Test fun fixedTemplatesObserveSyntaxIndependentlyOfTruth() {
        fun state(a: FixedTemplateAutomaton, word: List<UnaryOperator>): FixedTemplateAutomaton.State {
            var q = a.literalState("p"); for(op in word.asReversed()) q=a.unaryState(op,q); return q
        }
        val g = FixedTemplateAutomaton()
        assertTrue(g.isAccepting(state(g,listOf(UnaryOperator.G))))
        assertTrue(g.isAccepting(state(g,listOf(UnaryOperator.G,UnaryOperator.NOT))))
        assertFalse(g.isAccepting(state(g,listOf(UnaryOperator.G,UnaryOperator.F))))
        val r = FixedTemplateAutomaton(true)
        val prop = r.literalState("p")
        assertTrue(r.isAccepting(r.unaryState(UnaryOperator.G,r.binaryState(BinaryOperator.IMPLIES,prop,r.unaryState(UnaryOperator.F,prop)))))
        assertFalse(r.isAccepting(r.unaryState(UnaryOperator.G,r.binaryState(BinaryOperator.AND,prop,r.unaryState(UnaryOperator.F,prop)))))
    }

    @Test fun analyzerAcceptsOnlyCompleteCanonicalConstraints() {
        val forms = listOf(RecognizedConstraintAnalyzer.PROPOSITIONAL,RecognizedConstraintAnalyzer.NNF,RecognizedConstraintAnalyzer.CNF,
            RecognizedConstraintAnalyzer.DNF,RecognizedConstraintAnalyzer.GLOBAL_PROP,RecognizedConstraintAnalyzer.RESPONSE,
            "x0 in childrenAndSelfOf[root]","no l & r","all n: DAGNode | lone n.~(l+r)")
        for(body in forms) assertIs<MacroTaskAnalysis.Supported>(RecognizedConstraintAnalyzer.analyze(task("fact { $body }"),1),body)
        assertIs<MacroTaskAnalysis.Supported>(RecognizedConstraintAnalyzer.analyze(task(forms.take(2).joinToString("\n") { "fact { $it }" }),1))
        for(raw in listOf("fact { some DAGNode }","fact { ${RecognizedConstraintAnalyzer.NNF} no DAGNode }","fact { root in G } garbage",
            "/* NNF */ fact { #DAGNode = 2 }","one sig F0 extends F {} fact { maxsome[2] subDAG[root] & (F0->x0) }"))
            assertIs<MacroTaskAnalysis.Unsupported>(RecognizedConstraintAnalyzer.analyze(task(raw),1),raw)
        val repair = "one sig F0 extends F {} fact { root = F0 } fact { F0.l = x0 } fact { maxsome[2] subDAG[root] & (F0->x0) }"
        assertIs<MacroTaskAnalysis.Supported>(RecognizedConstraintAnalyzer.analyze(task(repair),0))
        fun reason(t: Task,b: Int?,minimum: Boolean=true) = (RecognizedConstraintAnalyzer.analyze(t,b,minimumSize=minimum) as MacroTaskAnalysis.Unsupported).reasons
        assertEquals(listOf(MacroUnsupportedReason.BINARY_TEMPORAL_UNTIL_REQUIRED),reason(task(excluded=emptyList()),1))
        assertEquals(listOf(MacroUnsupportedReason.BINARY_BUDGET_MISSING),reason(task(),null))
        assertEquals(listOf(MacroUnsupportedReason.UNSUPPORTED_OBJECTIVE),reason(task(),1,false))
        assertIs<MacroTaskAnalysis.Unsupported>(RecognizedConstraintAnalyzer.analyze(task("fact { root in G }",listOf("Until","G")),1))
    }

    @Test fun everyPaperConstrainedTaskHasAnExactMatchedPlan() {
        val expected = mapOf("peterson" to 30, "robot" to 20, "voting_machine" to 10, "weakening" to 78)
        for ((family,count) in expected) {
            val files = File("benchmark/$family").walkTopDown().filter { it.isFile && it.extension == "trace" }.toList()
            val parsed = files.mapNotNull { file -> runCatching { file to TaskParser.parseTask(file.readText()) }.getOrNull() }
            assertEquals(count,parsed.size,family)
            for ((file,original) in parsed) {
                val matched = original.copy(excludedOperators = (original.excludedOperators + "Until").distinct())
                val analysis = assertIs<MacroTaskAnalysis.Supported>(RecognizedConstraintAnalyzer.analyze(matched,2),file.path)
                assertEquals(if (family == "robot") null else UnaryOperator.G,
                    analysis.plan.requiredRootUnary,file.path)
            }
        }
        val finite = LassoTrace(prefix=listOf(State(mapOf("x0" to true)),State(emptyMap())))
        val positions = LassoPositions(finite,4)
        assertEquals(finite.length()-1,positions.loopStart)
        assertEquals(finite.length()-1,positions.successor.last())
    }
}
