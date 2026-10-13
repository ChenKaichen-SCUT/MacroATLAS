package cmu.s3d.ltl.macro.analysis

import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.AnchorExtractor
import cmu.s3d.ltl.macro.unary.UnaryOperator
import org.junit.jupiter.api.Test
import kotlin.test.*

class DagAnalysisTests {
    @Test
    fun allFiveBaseAutomataAndProductsEvaluateTheFullGraph() {
        val b = TestDags()
        val p = b.atom("p")
        val q = b.atom("q")
        val nq = b.chain("!", q)
        val root = b.binary(BinaryOperator.AND, p, nq)
        val dag = b.dag(root)
        val nnf = NnfAutomaton()
        val cnf = CnfAutomaton()
        val dnf = DnfAutomaton()
        val prop = PropositionalAutomaton()
        val required = RequiredPropositionAutomaton("p")
        assertEquals(NnfAutomaton.State.VALID_NON_ATOM, DagConstraintEvaluator(nnf).evaluate(dag).rootState)
        assertEquals(CnfAutomaton.State.CNF, DagConstraintEvaluator(cnf).evaluate(dag).rootState)
        assertEquals(DnfAutomaton.State.TERM, DagConstraintEvaluator(dnf).evaluate(dag).rootState)
        assertEquals(PropositionalAutomaton.State.PROP, DagConstraintEvaluator(prop).evaluate(dag).rootState)
        assertEquals(RequiredPropositionAutomaton.State.PRESENT, DagConstraintEvaluator(required).evaluate(dag).rootState)
        val product = ProductConstraintAutomaton(listOf(nnf, cnf, dnf, prop, required))
        val evaluation = DagConstraintEvaluator(product).evaluate(dag)
        assertEquals(dag.nodes.keys, evaluation.stateByNode.keys)
        assertTrue(product.isAccepting(evaluation.rootState))
        assertEquals(listOf(NnfAutomaton.State.VALID_NON_ATOM, CnfAutomaton.State.CNF, DnfAutomaton.State.TERM,
            PropositionalAutomaton.State.PROP, RequiredPropositionAutomaton.State.PRESENT), evaluation.rootState.components)
        assertFailsWith<UnsupportedOperationException> { (evaluation.stateByNode as MutableMap).clear() }
    }

    @Test
    fun literalAndValidAndInvalidUnaryRootsKeepTheirFullStates() {
        val nnf = NnfAutomaton()
        for ((word, expected) in listOf("" to NnfAutomaton.State.ATOM, "!" to NnfAutomaton.State.VALID_NON_ATOM,
            "G!" to NnfAutomaton.State.VALID_NON_ATOM, "!G" to NnfAutomaton.State.INVALID)) {
            val b = TestDags()
            val root = b.chain(word, b.atom())
            val result = DagConstraintEvaluator(nnf).evaluate(b.dag(root))
            assertEquals(expected, result.rootState)
            assertEquals(word.length + 1, result.stateByNode.size)
            assertTrue(MacroEligibilityAnalyzer(nnf).analyze(b.dag(root)) is MacroEligibility.Eligible)
        }
    }

    @Test
    fun sharedSubtreesAreEvaluatedOnceEvenWhenReferencedBySeveralParentsAndPorts() {
        val b = TestDags()
        val p = b.atom()
        val shared = b.chain("G!", p)
        val left = b.binary(BinaryOperator.AND, shared, shared)
        val right = b.chain("F", shared)
        val dag = b.dag(b.binary(BinaryOperator.OR, left, right))
        var literals = 0
        var unary = 0
        var binary = 0
        val counting = object : ConstraintAutomaton<Int> {
            override fun literalState(proposition: String): Int { literals++; return 1 }
            override fun unaryState(operator: UnaryOperator, child: Int): Int { unary++; return child + 1 }
            override fun binaryState(operator: BinaryOperator, left: Int, right: Int): Int { binary++; return left + right + 1 }
            override fun isAccepting(state: Int) = true
        }
        val evaluation = DagConstraintEvaluator(counting).evaluate(dag)
        assertEquals(1, literals)
        assertEquals(3, unary)
        assertEquals(2, binary)
        assertEquals(6, evaluation.stateByNode.size)
        assertEquals(3, dag.indegree(shared))
        assertEquals(2, dag.parents(shared).size)
    }

    @Test
    fun eligibilityReturnsAllStructuralProfileReasonsAndDoesNotConfuseLabelsWithIds() {
        val b = TestDags()
        val p = b.atom()
        val g = b.unary(UnaryOperator.G, p, "G\$0")
        val dag = b.dag(b.binary(BinaryOperator.UNTIL, p, g))
        val result = MacroEligibilityAnalyzer(NnfAutomaton()).analyze(dag, listOf(NodeId("G")),
            listOf(UnaryOperator.NOT), "fact { some G }")
        assertTrue(result is MacroEligibility.Unsupported)
        assertEquals(setOf(MacroEligibility.Code.UNTIL, MacroEligibility.Code.DISALLOWED_UNARY,
            MacroEligibility.Code.UNKNOWN_PROTECTED_NODE, MacroEligibility.Code.UNHANDLED_ALLOY_CONSTRAINTS),
            result.reasons.map { it.code }.toSet())
        assertFailsWith<MacroIneligibleException> { AnchorExtractor.extract(result) }
        assertFailsWith<UnsupportedOperationException> { (result.reasons as MutableList).clear() }
    }

    @Test
    fun unknownRawAlloyIsRejectedEvenWhenEveryNodeIsProtected() {
        val b = TestDags()
        val dag = b.dag(b.chain("FF", b.atom()))
        val analyzer = MacroEligibilityAnalyzer(NnfAutomaton())
        for (text in listOf("fact { #F = 2 }", "fact { root.l in F }", "minsome subDAG[root]")) {
            val result = analyzer.analyze(dag, dag.nodes.keys, unhandledAlloyConstraints = text)
            assertTrue(result is MacroEligibility.Unsupported)
            assertEquals(MacroEligibility.Code.UNHANDLED_ALLOY_CONSTRAINTS, result.reasons.single().code)
        }
        assertTrue(analyzer.analyze(dag, unhandledAlloyConstraints = " \n ") is MacroEligibility.Eligible)
    }

    @Test
    fun nonTotalAutomataAreUnsupportedAndEligibilitySnapshotsAreImmutable() {
        val b = TestDags()
        val dag = b.dag(b.chain("F", b.atom()))
        val broken = object : ConstraintAutomaton<Int> {
            override fun literalState(proposition: String) = 0
            override fun unaryState(operator: UnaryOperator, child: Int): Int = error("missing unary transition")
            override fun binaryState(operator: BinaryOperator, left: Int, right: Int) = 0
            override fun isAccepting(state: Int) = true
        }
        val bad = MacroEligibilityAnalyzer(broken).analyze(dag)
        assertTrue(bad is MacroEligibility.Unsupported)
        assertEquals(MacroEligibility.Code.AUTOMATON_EVALUATION_FAILED, bad.reasons.single().code)
        val protected = mutableSetOf(dag.root)
        val alphabet = mutableListOf(UnaryOperator.F)
        val result = MacroEligibilityAnalyzer(NnfAutomaton()).analyze(dag, protected, alphabet)
        assertTrue(result is MacroEligibility.Eligible)
        protected.clear()
        alphabet.clear()
        assertEquals(setOf(dag.root), result.protectedNodeIds)
        assertEquals(listOf(UnaryOperator.F), result.allowedUnaryOperators)
        assertFailsWith<UnsupportedOperationException> { (result.protectedNodeIds as MutableSet).clear() }
        assertFailsWith<UnsupportedOperationException> { (result.allowedUnaryOperators as MutableList).clear() }
    }
}
