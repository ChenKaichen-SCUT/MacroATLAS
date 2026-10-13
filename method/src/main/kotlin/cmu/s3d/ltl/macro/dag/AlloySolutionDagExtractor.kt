package cmu.s3d.ltl.macro.dag

import cmu.s3d.ltl.learning.LTLLearningSolution
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.unary.UnaryOperator
import java.util.ArrayDeque

/** Read-only bridge from a real Alloy solution; never calls getLTL/getLTL2 or unfolds sharing. */
class AlloySolutionDagExtractor {
    /** Snapshot only the reachable formula, preserving full Alloy atom strings as NodeIds. */
    fun extract(solution: LTLLearningSolution): FormulaDag = extract(solution.getRoot(), solution::getNodeAndChildren)

    // Read seam for testing memoization and malformed Alloy node descriptions.
    internal fun extract(rootAtom: String, read: (String) -> LTLLearningSolution.Node): FormulaDag {
        val nodes = LinkedHashMap<NodeId, FormulaNode>()
        val pending = ArrayDeque<String>()
        pending.add(rootAtom)
        while (pending.isNotEmpty()) {
            val atom = pending.removeFirst()
            val id = NodeId(atom)
            if (id in nodes) continue
            val description = read(atom)
            val left = description.left
            val right = description.right
            // ATLAS strips numbered operator signature suffixes, but never literal digits.
            val operatorName = description.name.replace("\\d+$".toRegex(), "")
            nodes[id] = when {
                left == null && right == null -> LiteralNode(id, description.name)
                left != null && right == null -> UnaryNode(id, UnaryOperator.fromAtlas(operatorName), NodeId(left))
                left != null && right != null -> BinaryNode(id, BinaryOperator.fromAtlas(operatorName), NodeId(left), NodeId(right))
                else -> throw IllegalArgumentException("Right-only child at Alloy atom $atom")
            }
            if (left != null) pending.addLast(left)
            if (right != null) pending.addLast(right)
        }
        return FormulaDag(NodeId(rootAtom), nodes)
    }
}
