package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.analysis.*
import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.macro.word
import org.junit.jupiter.api.Test
import kotlin.random.Random
import kotlin.test.*

class MacroKernelTests {
    private fun <Q : Any> compress(dag: FormulaDag, automaton: ConstraintAutomaton<Q>, protected: Set<NodeId> = emptySet()): MacroDag<Q> =
        FiberMacroCanonicalizer.canonicalize(AnchorExtractor.extract(MacroEligibilityAnalyzer(automaton).analyze(dag, protected)))

    private fun <Q : Any> verify(dag: FormulaDag, macro: MacroDag<Q>): FormulaDag {
        val result = MacroRoundTripVerifier.verify(dag, macro)
        assertTrue(result.isValid, "${result.violations}\n$dag")
        assertEquals(dag, MacroDagExpander.expandOriginal(macro))
        assertTrue(macro.statistics.numberOfPorts <= macro.statistics.kernelBudget)
        return assertNotNull(result.canonicalDag)
    }

    @Test
    fun unprotectedRootChainIsAbsorbedByTheVirtualRootPort() {
        val b = TestDags()
        val p = b.atom()
        val dag = b.dag(b.chain("FXG", p))
        val raw = AnchorExtractor.extract(MacroEligibilityAnalyzer(NnfAutomaton()).analyze(dag))
        assertEquals(setOf(p), raw.actualAnchors.keys)
        assertEquals(1, raw.edgesByPort.size)
        val edge = raw.edgesByPort.getValue(MacroPort.ROOT)
        assertEquals(word("FXG"), edge.originalWord)
        assertEquals(p, edge.target)
        assertEquals(dag.root, edge.originalInternalNodeIds.first())
        assertEquals(dag, MacroDagExpander.expandOriginal(raw))
        assertEquals(1, raw.statistics.numberOfPorts)
        verify(dag, FiberMacroCanonicalizer.canonicalize(raw))
    }

    @Test
    fun twoBranchExampleShrinksFromSevenNodesToFive() {
        val b = TestDags()
        val p = b.atom("x0", "x0")
        val q = b.atom("x1", "x1")
        val root = b.binary(BinaryOperator.AND, b.chain("FF", p), b.chain("GG", q), "And0")
        val dag = b.dag(root)
        val macro = compress(dag, NnfAutomaton())
        val canonical = verify(dag, macro)
        assertEquals(7, dag.size())
        assertEquals(5, canonical.size())
        assertEquals("&(F(x0),G(x1))", FormulaDagRenderer.render(canonical))
        assertEquals(setOf(root, p, q), macro.actualAnchors.keys)
        assertEquals(word(""), macro.edgesByPort.getValue(MacroPort.ROOT).representativeWord)
        assertEquals(word("F"), macro.edgesByPort.getValue(MacroPort(root, PortKind.LEFT)).representativeWord)
        assertEquals(word("G"), macro.edgesByPort.getValue(MacroPort(root, PortKind.RIGHT)).representativeWord)
        assertEquals(KernelStatistics(1, 0, 0, 3, 3, 3, 2, 7, 5), macro.statistics)
    }

    @Test
    fun directEdgesAndRepeatedLiteralTargetsRemainSharedAndEmpty() {
        val b = TestDags()
        val p = b.atom()
        val root = b.binary(BinaryOperator.OR, p, p)
        val dag = b.dag(root)
        val macro = compress(dag, CnfAutomaton())
        val canonical = verify(dag, macro)
        assertEquals(dag, canonical)
        assertTrue(macro.edgesByPort.values.all { it.originalWord.isEmpty() && it.representativeWord.isEmpty() })
        assertEquals(p, macro.edgesByPort.getValue(MacroPort(root, PortKind.LEFT)).target)
        assertEquals(p, macro.edgesByPort.getValue(MacroPort(root, PortKind.RIGHT)).target)
        assertEquals(2, canonical.size())
    }

    @Test
    fun sameParentTwoPortsMakeTheirSharedUnaryChildAnAnchor() {
        val b = TestDags()
        val p = b.atom()
        val shared = b.chain("FFF", p)
        val dag = b.dag(b.binary(BinaryOperator.AND, shared, shared))
        val macro = compress(dag, NnfAutomaton())
        val canonical = verify(dag, macro)
        assertTrue(shared in macro.actualAnchors)
        assertTrue(macro.edgesByPort.values.none { shared in it.originalInternalNodeIds })
        val root = canonical.node(canonical.root) as BinaryNode
        assertEquals(shared, root.left)
        assertEquals(shared, root.right)
        assertEquals(2, canonical.indegree(shared))
        assertEquals(4, canonical.size())
        assertEquals(1, macro.statistics.u)
    }

    @Test
    fun differentParentsPreserveTheSameSharedUnaryIdentity() {
        val b = TestDags()
        val shared = b.chain("GG", b.atom())
        val left = b.chain("F", shared)
        val right = b.chain("X", shared)
        val dag = b.dag(b.binary(BinaryOperator.IMPLIES, left, right))
        val macro = compress(dag, NnfAutomaton())
        val canonical = verify(dag, macro)
        assertEquals(2, dag.parents(shared).size)
        assertTrue(shared in canonical.nodes)
        assertEquals(2, macro.edgesByPort.values.count { it.target == shared })
        assertEquals(2, canonical.indegree(shared))
    }

    @Test
    fun protectedInteriorAndProtectedRootCutPathsAtTheirExactIdentities() {
        val b = TestDags()
        val p = b.atom()
        val inner = b.chain("FF", p)
        val root = b.chain("FF", inner)
        val dag = b.dag(root)
        val middleProtected = compress(dag, NnfAutomaton(), setOf(inner))
        val canonical = verify(dag, middleProtected)
        assertEquals(setOf(inner, p), middleProtected.actualAnchors.keys)
        assertEquals(2, middleProtected.edgesByPort.size)
        assertTrue(dag.node(inner).sameIdentityAndLabel(canonical.node(inner)))
        assertTrue(middleProtected.edgesByPort.values.none { inner in it.originalInternalNodeIds })
        val rootProtected = compress(dag, NnfAutomaton(), setOf(root, inner, p))
        val protectedCanonical = verify(dag, rootProtected)
        assertEquals(root, protectedCanonical.root)
        assertTrue(rootProtected.edgesByPort.getValue(MacroPort.ROOT).representativeWord.isEmpty())
        assertEquals(3, rootProtected.statistics.p)
        assertEquals(2, rootProtected.statistics.u)
    }

    @Test
    fun nnfEquivalentContextsRetainDifferentFibersAndNonacceptingState() {
        val b = TestDags()
        val p = b.atom()
        val invalid = b.chain("!G", p)
        val valid = b.chain("F!", p)
        val root = b.binary(BinaryOperator.OR, invalid, valid)
        val dag = b.dag(root)
        val macro = compress(dag, NnfAutomaton())
        val left = macro.edgesByPort.getValue(MacroPort(root, PortKind.LEFT))
        val right = macro.edgesByPort.getValue(MacroPort(root, PortKind.RIGHT))
        assertEquals(left.fiberKey.semanticType, right.fiberKey.semanticType)
        assertNotEquals(left.fiberKey, right.fiberKey)
        assertEquals(word("!G"), left.representativeWord)
        assertEquals(word("F!"), right.representativeWord)
        assertEquals(NnfAutomaton.State.INVALID, macro.constraintRootState)
        verify(dag, macro)
    }

    @Test
    fun emptyAndNonemptyIdentityContextsNeverMerge() {
        val b = TestDags()
        val p = b.atom()
        val root = b.binary(BinaryOperator.AND, p, b.chain("!!!!", p))
        val dag = b.dag(root)
        val macro = compress(dag, PropositionalAutomaton())
        val left = macro.edgesByPort.getValue(MacroPort(root, PortKind.LEFT))
        val right = macro.edgesByPort.getValue(MacroPort(root, PortKind.RIGHT))
        assertEquals(left.fiberKey.semanticType, right.fiberKey.semanticType)
        assertFalse(left.fiberKey.nonEmpty)
        assertTrue(right.fiberKey.nonEmpty)
        assertEquals(word("!!"), right.representativeWord)
        verify(dag, macro)
    }

    @Test
    fun productOwnerAndAllPortStateCrossChecksStayConsistent() {
        val b = TestDags()
        val p = b.atom()
        val shared = b.chain("G!", p)
        val root = b.binary(BinaryOperator.OR, b.chain("FFF", shared), shared)
        val dag = b.dag(root)
        val product = ProductConstraintAutomaton(listOf(NnfAutomaton(), RequiredPropositionAutomaton("p"), PropositionalAutomaton()))
        val raw = AnchorExtractor.extract(MacroEligibilityAnalyzer(product).analyze(dag))
        val macro = FiberMacroCanonicalizer.canonicalize(raw)
        verify(dag, macro)
        for ((port, edge) in macro.edgesByPort) {
            assertSame(raw.evaluation.stateByNode[edge.target], edge.fiberKey.qIn)
            assertEquals(raw.evaluation.stateByNode[immediateChild(dag, port)], edge.fiberKey.qOut)
        }
        assertFalse(product.isAccepting(macro.constraintRootState))
    }

    @Test
    fun decompositionAndFreshIdsAreDeterministicAcrossMapOrdersAndAvoidCollisions() {
        val b = TestDags()
        val collision = b.atom("p", "__macro__/virtual/ROOT/0")
        val root = b.chain("FF", collision)
        val dag = b.dag(root)
        val profile = NnfAutomaton()
        val baseline = compress(dag, profile)
        val canonical = verify(dag, baseline)
        assertEquals(NodeId("__macro__/virtual/ROOT/0~1"), canonical.root)
        assertTrue(collision in canonical.nodes)
        val random = Random(412)
        repeat(20) {
            val shuffled = FormulaDag(root, b.nodes.values.shuffled(random).associateBy { it.id })
            val macro = compress(shuffled, profile)
            assertEquals(baseline.edgesByPort, macro.edgesByPort)
            assertEquals(baseline.statistics, macro.statistics)
            assertEquals(canonical, MacroDagExpander.expandCanonical(macro))
        }
    }

    @Test
    fun portsUseSourceIdentityAndSnapshotsAreImmutable() {
        assertNotEquals(MacroPort(NodeId("a"), PortKind.LEFT), MacroPort(NodeId("b"), PortKind.LEFT))
        assertFailsWith<IllegalArgumentException> { MacroPort(null, PortKind.LEFT) }
        assertFailsWith<IllegalArgumentException> { MacroPort(NodeId("root"), PortKind.ROOT) }
        val b = TestDags()
        val dag = b.dag(b.chain("FF", b.atom()))
        val raw = AnchorExtractor.extract(MacroEligibilityAnalyzer(NnfAutomaton()).analyze(dag))
        val macro = FiberMacroCanonicalizer.canonicalize(raw)
        assertFailsWith<UnsupportedOperationException> { (raw.actualAnchors as MutableMap).clear() }
        assertFailsWith<UnsupportedOperationException> { (raw.edgesByPort as MutableMap).clear() }
        assertFailsWith<UnsupportedOperationException> { (raw.edgesByPort.values.first().originalInternalNodeIds as MutableList).clear() }
        assertFailsWith<UnsupportedOperationException> { (macro.edgesByPort as MutableMap).clear() }
        assertFailsWith<UnsupportedOperationException> { (macro.protectedNodeIds as MutableSet).clear() }
        assertFailsWith<UnsupportedOperationException> { (macro.allowedUnaryOperators as MutableList).clear() }
    }

    @Test
    fun verifierReturnsStructuredViolationsForBrokenWordsSkeletonIdentityAndCounts() {
        val b = TestDags()
        val p = b.atom()
        val dag = b.dag(b.chain("FFF", p))
        val macro = compress(dag, NnfAutomaton())
        fun changed(
            edges: Map<MacroPort, CanonicalMacroEdge<NnfAutomaton.State>> = macro.edgesByPort,
            anchors: Map<NodeId, FormulaNode> = macro.actualAnchors,
            protected: Collection<NodeId> = macro.protectedNodeIds,
            count: Int = macro.originalNodeCount,
            state: NnfAutomaton.State = macro.constraintRootState
        ) = MacroDag(anchors, edges, protected, count, state, macro.allowedUnaryOperators, macro.automaton)
        val edge = macro.edgesByPort.getValue(MacroPort.ROOT)
        val badWord = changed(edges = mapOf(MacroPort.ROOT to edge.copy(representativeWord = word("G"))))
        val wordResult = MacroRoundTripVerifier.verify(dag, badWord)
        assertFalse(wordResult.isValid)
        assertTrue(wordResult.violations.any { it.code == MacroViolation.Code.FIBER_REPLAY })
        assertTrue(MacroRoundTripVerifier.verify(dag, changed(edges = emptyMap())).violations.any { it.code == MacroViolation.Code.CANONICAL_STRUCTURE })
        assertTrue(MacroRoundTripVerifier.verify(dag, changed(anchors = mapOf(p to LiteralNode(p, "q")))).violations.any { it.code == MacroViolation.Code.ANCHOR_IDENTITY })
        assertTrue(MacroRoundTripVerifier.verify(dag, changed(protected = listOf(dag.root))).violations.any { it.code == MacroViolation.Code.PROTECTED_IDENTITY })
        assertTrue(MacroRoundTripVerifier.verify(dag, changed(count = 1)).violations.any { it.code == MacroViolation.Code.NODE_COUNT })
        assertTrue(MacroRoundTripVerifier.verify(dag, changed(state = NnfAutomaton.State.INVALID)).violations.any { it.code == MacroViolation.Code.ROOT_STATE })
        val longer = changed(edges = mapOf(MacroPort.ROOT to edge.copy(representativeWord = word("FF"))))
        assertTrue(MacroRoundTripVerifier.verify(dag, longer).violations.any { it.code == MacroViolation.Code.REPRESENTATIVE })
        assertFailsWith<UnsupportedOperationException> { (wordResult.violations as MutableList).clear() }
    }
}
