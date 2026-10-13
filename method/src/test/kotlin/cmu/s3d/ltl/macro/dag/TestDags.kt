package cmu.s3d.ltl.macro.dag

import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Test fixtures construct identity graphs directly, without parsing displayed formulas. */
internal class TestDags {
    val nodes = linkedMapOf<NodeId, FormulaNode>()
    fun atom(name: String = "p", id: String = "a${nodes.size}"): NodeId = add(LiteralNode(NodeId(id), name))
    fun unary(op: UnaryOperator, child: NodeId, id: String = "u${nodes.size}"): NodeId = add(UnaryNode(NodeId(id), op, child))
    fun binary(op: BinaryOperator, left: NodeId, right: NodeId, id: String = "b${nodes.size}"): NodeId =
        add(BinaryNode(NodeId(id), op, left, right))
    fun chain(word: String, child: NodeId): NodeId {
        var root = child
        for (symbol in word.toList().asReversed()) root = unary(UnaryOperator.fromAtlas(symbol.toString()), root)
        return root
    }
    fun dag(root: NodeId): FormulaDag = FormulaDag(root, nodes)
    private fun add(node: FormulaNode): NodeId {
        check(nodes.put(node.id, node) == null)
        return node.id
    }
}
