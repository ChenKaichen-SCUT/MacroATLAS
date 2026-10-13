package cmu.s3d.ltl.macro.dag

import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Immutable node types enforce arity; references preserve DAG sharing by identity. */
sealed class FormulaNode {
    /** Identity of this node, not its label. */
    abstract val id: NodeId

    /** Ordered outgoing references; a binary node may repeat the same child twice. */
    fun children(): List<NodeId> = immutableList(when (this) {
        is LiteralNode -> emptyList()
        is UnaryNode -> listOf(child)
        is BinaryNode -> listOf(left, right)
    })

    /** Compare identity, node kind and label, allowing outgoing references to change. */
    fun sameIdentityAndLabel(other: FormulaNode): Boolean = id == other.id && when (this) {
        is LiteralNode -> other is LiteralNode && proposition == other.proposition
        is UnaryNode -> other is UnaryNode && operator == other.operator
        is BinaryNode -> other is BinaryNode && operator == other.operator
    }
}

/** Atomic proposition with its original ATLAS String identity. */
data class LiteralNode(override val id: NodeId, val proposition: String) : FormulaNode()

/** One unary operator applied to one child. */
data class UnaryNode(override val id: NodeId, val operator: UnaryOperator, val child: NodeId) : FormulaNode()

/** Ordered binary operator; U is representable here but rejected by macro eligibility. */
data class BinaryNode(
    override val id: NodeId,
    val operator: BinaryOperator,
    val left: NodeId,
    val right: NodeId
) : FormulaNode()
