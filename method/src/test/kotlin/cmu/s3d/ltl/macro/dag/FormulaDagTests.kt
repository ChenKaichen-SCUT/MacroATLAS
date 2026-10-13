package cmu.s3d.ltl.macro.dag

import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.unary.UnaryOperator
import org.junit.jupiter.api.Test
import kotlin.test.*

class FormulaDagTests {
    @Test
    fun literalUnaryBinaryAndSharedChildrenHaveCorrectStructure() {
        val b = TestDags()
        val p = b.atom("p", "p\$0")
        val unary = b.chain("!X", p)
        val root = b.binary(BinaryOperator.AND, unary, unary)
        val dag = b.dag(root)
        FormulaDagValidator.validate(dag)
        assertEquals("&(!(X(p)),!(X(p)))", FormulaDagRenderer.render(dag))
        assertEquals(listOf(unary, unary), dag.children(root))
        assertEquals(setOf(root), dag.parents(unary))
        assertEquals(2, dag.indegree(unary)) // Two ports from ONE parent are still sharing.
        assertEquals(0, dag.indegree(root))
        assertEquals(4, dag.size())
        assertEquals(4, dag.postOrder().distinct().size)
        assertEquals(root, dag.postOrder().last())
        assertEquals(dag.nodes.keys, dag.reachableNodes())
        val single = FormulaDag(p, listOf(LiteralNode(p, "p")))
        assertEquals("p", FormulaDagRenderer.render(single))
        assertTrue(single.children(p).isEmpty())
    }

    @Test
    fun missingRootChildCycleUnreachableDuplicatesAndBlankPropositionsAreRejected() {
        val p = NodeId("p")
        val u = NodeId("u")
        fun rejects(reason: String, block: () -> Unit) {
            assertTrue(assertFailsWith<IllegalArgumentException>(block = block).message!!.contains(reason))
        }
        rejects("Missing root") { FormulaDag(p, emptyMap()) }
        rejects("Missing child") { FormulaDag(u, listOf(UnaryNode(u, UnaryOperator.F, p))) }
        rejects("Cycle") { FormulaDag(u, listOf(UnaryNode(u, UnaryOperator.F, u))) }
        rejects("Cycle") { FormulaDag(u, listOf(UnaryNode(u, UnaryOperator.F, p), UnaryNode(p, UnaryOperator.G, u))) }
        rejects("Unreachable") { FormulaDag(p, listOf(LiteralNode(p, "p"), LiteralNode(u, "q"))) }
        rejects("Duplicate") { FormulaDag(p, listOf(LiteralNode(p, "p"), LiteralNode(p, "p"))) }
        rejects("does not match") { FormulaDag(p, mapOf(p to LiteralNode(u, "p"))) }
        rejects("Empty proposition") { FormulaDag(p, listOf(LiteralNode(p, "   "))) }
        rejects("must not be blank") { NodeId("") }
        rejects("Unknown node") { FormulaDag(p, listOf(LiteralNode(p, "p"))).node(u) }
    }

    @Test
    fun graphOrderAndEqualityAreIndependentOfMapInsertionOrder() {
        val b = TestDags()
        val p = b.atom()
        val left = b.chain("FG", p)
        val right = b.chain("X!", p)
        val root = b.binary(BinaryOperator.IMPLIES, left, right)
        val dag = b.dag(root)
        val reversed = FormulaDag(root, b.nodes.values.toList().asReversed().associateBy { it.id })
        assertEquals(dag, reversed)
        assertEquals(dag.hashCode(), reversed.hashCode())
        assertEquals(dag.nodes.keys.toList(), reversed.nodes.keys.toList())
        assertEquals(dag.postOrder(), reversed.postOrder())
        assertEquals(FormulaDagRenderer.render(dag), FormulaDagRenderer.render(reversed))
    }

    @Test
    fun snapshotsCannotBeMutatedThroughSourceCollectionsOrViews() {
        val p = NodeId("p")
        val root = NodeId("root")
        val source = linkedMapOf<NodeId, FormulaNode>(p to LiteralNode(p, "p"), root to BinaryNode(root, BinaryOperator.OR, p, p))
        val dag = FormulaDag(root, source)
        source.clear()
        assertEquals(2, dag.size())
        assertFailsWith<UnsupportedOperationException> { (dag.nodes as MutableMap).clear() }
        assertFailsWith<UnsupportedOperationException> { (dag.parents(p) as MutableSet).clear() }
        assertFailsWith<UnsupportedOperationException> { (dag.postOrder() as MutableList).clear() }
        assertFailsWith<UnsupportedOperationException> { (dag.children(root) as MutableList)[0] = root }
        assertFailsWith<UnsupportedOperationException> { (dag.reachableNodes() as MutableSet).clear() }
    }

    @Test
    fun deepDagsAndDeepCyclesUseIterativeValidation() {
        val nodes = ArrayList<FormulaNode>()
        nodes.add(LiteralNode(NodeId("0"), "p"))
        for (i in 1..12000) nodes.add(UnaryNode(NodeId(i.toString()), UnaryOperator.X, NodeId((i - 1).toString())))
        val dag = FormulaDag(NodeId("12000"), nodes)
        assertEquals(12001, dag.postOrder().size)
        nodes[0] = UnaryNode(NodeId("0"), UnaryOperator.F, NodeId("12000"))
        assertTrue(assertFailsWith<IllegalArgumentException> { FormulaDag(NodeId("12000"), nodes) }.message!!.contains("Cycle"))
    }
}
