package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Independent test-only U-free semantics; does not call normalizer, fiber table or macro code. */
internal object UFreeLassoOracle {
    fun evaluate(dag: FormulaDag, trace: LassoTrace): BooleanArray {
        require(trace.loop.isNotEmpty()) { "An infinite lasso needs a nonempty loop" }
        val size = trace.length()
        fun successor(i: Int): Int = if (i == size - 1) trace.prefix.size else i + 1
        val states = HashMap<NodeId, BooleanArray>()
        for (id in dag.postOrder()) states[id] = when (val node = dag.node(id)) {
            is LiteralNode -> BooleanArray(size) { trace.getStateAt(it).values.getValue(node.proposition) }
            is UnaryNode -> {
                val child = states.getValue(node.child)
                BooleanArray(size) { start -> when (node.operator) {
                    UnaryOperator.NOT -> !child[start]
                    UnaryOperator.X -> child[successor(start)]
                    UnaryOperator.F, UnaryOperator.G -> {
                        val visited = BooleanArray(size)
                        var position = start
                        var value = node.operator == UnaryOperator.G
                        while (!visited[position]) {
                            visited[position] = true
                            value = if (node.operator == UnaryOperator.G) value && child[position] else value || child[position]
                            position = successor(position)
                        }
                        value
                    }
                } }
            }
            is BinaryNode -> {
                val left = states.getValue(node.left)
                val right = states.getValue(node.right)
                require(node.operator != BinaryOperator.UNTIL) { "Test oracle is U-free" }
                BooleanArray(size) { i -> when (node.operator) {
                    BinaryOperator.AND -> left[i] && right[i]
                    BinaryOperator.OR -> left[i] || right[i]
                    BinaryOperator.IMPLIES -> !left[i] || right[i]
                    BinaryOperator.UNTIL -> error("U is unsupported")
                } }
            }
        }
        return states.getValue(dag.root)
    }
}
