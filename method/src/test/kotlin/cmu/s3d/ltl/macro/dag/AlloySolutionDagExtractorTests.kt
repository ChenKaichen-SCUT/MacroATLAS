package cmu.s3d.ltl.macro.dag

import cmu.s3d.ltl.learning.LTLLearningSolution
import cmu.s3d.ltl.macro.analysis.MacroEligibility
import cmu.s3d.ltl.macro.analysis.MacroEligibilityAnalyzer
import cmu.s3d.ltl.macro.constraint.NnfAutomaton
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.kernel.*
import cmu.s3d.ltl.samples2ltl.TaskParser
import org.junit.jupiter.api.Test
import kotlin.test.*

class AlloySolutionDagExtractorTests {
    private fun task(name: String) = TaskParser.parseTask(ClassLoader.getSystemResource("samples2ltl/$name.trace").readText())

    @Test
    fun realSampleExtractsRendersAndCompletesTheMacroRoundTrip() {
        val task = task("example0000")
        val solution = assertNotNull(task.buildLearner().learn())
        val dag = AlloySolutionDagExtractor().extract(solution)
        assertEquals(solution.getLTL2(), FormulaDagRenderer.render(dag))
        assertEquals(NodeId(solution.getRoot()), dag.root)
        FormulaDagValidator.validate(dag)
        for ((id, node) in dag.nodes) {
            val original = solution.getNodeAndChildren(id.value)
            assertEquals(listOfNotNull(original.left, original.right), node.children().map { it.value })
            assertTrue(id.value.contains('$'))
        }
        val raw = AnchorExtractor.extract(MacroEligibilityAnalyzer(NnfAutomaton()).analyze(dag,
            unhandledAlloyConstraints = task.customConstraints))
        assertTrue(MacroRoundTripVerifier.verify(dag, FiberMacroCanonicalizer.canonicalize(raw)).isValid)
    }

    @Test
    fun actualAlloySharingIsRetainedAndRawConstraintsAreNotSilentlyClaimed() {
        val task = task("example0000").copy(maxNumOfOP = 5, customConstraints = """
            fact {
                root in And
                root.l = root.r
                root.l in Neg
                root.l.l in F
                root.l.l.l = x0
            }
        """.trimIndent())
        val solution = assertNotNull(task.buildLearner().learn())
        val dag = AlloySolutionDagExtractor().extract(solution)
        assertEquals(solution.getLTL2(), FormulaDagRenderer.render(dag))
        val root = dag.node(dag.root) as BinaryNode
        assertEquals(root.left, root.right)
        assertTrue(dag.node(root.left) is UnaryNode)
        assertEquals(2, dag.indegree(root.left))
        assertEquals(4, dag.size())
        val eligibility = MacroEligibilityAnalyzer(NnfAutomaton()).analyze(dag, unhandledAlloyConstraints = task.customConstraints)
        assertTrue(eligibility is MacroEligibility.Unsupported)
        assertTrue(eligibility.reasons.any { it.code == MacroEligibility.Code.UNHANDLED_ALLOY_CONSTRAINTS })
    }

    @Test
    fun untilRemainsRepresentableFromARealSolutionButIsIneligible() {
        val solution = assertNotNull(task("example0007").buildLearner().learn())
        val dag = AlloySolutionDagExtractor().extract(solution)
        assertEquals(solution.getLTL2(), FormulaDagRenderer.render(dag))
        assertTrue(dag.nodes.values.any { it is BinaryNode && it.operator == BinaryOperator.UNTIL })
        val result = MacroEligibilityAnalyzer(NnfAutomaton()).analyze(dag)
        assertTrue(result is MacroEligibility.Unsupported)
        assertTrue(result.reasons.any { it.code == MacroEligibility.Code.UNTIL })
        assertFailsWith<IllegalArgumentException> { AnchorExtractor.extract(result) }
    }

    @Test
    fun adapterReadsEachFullAtomOnceAndSeparatesNumberedLabelsFromIdentity() {
        val descriptions = mapOf(
            "And0\$4" to LTLLearningSolution.Node("And0", "G12\$1", "G12\$1"),
            "G12\$1" to LTLLearningSolution.Node("G12", "x10\$3", null),
            "x10\$3" to LTLLearningSolution.Node("x10", null, null)
        )
        val reads = HashMap<String, Int>()
        val dag = AlloySolutionDagExtractor().extract("And0\$4") {
            reads[it] = (reads[it] ?: 0) + 1
            descriptions.getValue(it)
        }
        assertEquals(descriptions.keys.associateWith { 1 }, reads)
        assertEquals(descriptions.keys.map(::NodeId).toSet(), dag.nodes.keys)
        assertEquals("&(G(x10),G(x10))", FormulaDagRenderer.render(dag))
        assertEquals(2, dag.indegree(NodeId("G12\$1")))
    }

    @Test
    fun malformedAdapterArityAndCyclesFailExplicitly() {
        assertFailsWith<IllegalArgumentException> {
            AlloySolutionDagExtractor().extract("bad\$0") { LTLLearningSolution.Node("F", null, "p\$0") }
        }
        assertFailsWith<IllegalArgumentException> {
            AlloySolutionDagExtractor().extract("bad\$0") { LTLLearningSolution.Node("Until", "p\$0", null) }
        }
        assertFailsWith<IllegalArgumentException> {
            AlloySolutionDagExtractor().extract("G\$0") { LTLLearningSolution.Node("G", "G\$0", null) }
        }
    }
}
