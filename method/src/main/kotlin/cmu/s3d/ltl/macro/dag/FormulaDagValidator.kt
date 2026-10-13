package cmu.s3d.ltl.macro.dag

import java.util.ArrayDeque

/** Structural validation using iterative DFS, including cycles in arbitrarily deep chains. */
object FormulaDagValidator {
    /** Revalidate a graph; failures are IllegalArgumentException with an explicit reason. */
    fun validate(dag: FormulaDag) { validate(dag.root, dag.nodes) }

    /** Validate a proposed graph and return its deterministic children-before-parent order. */
    fun validate(root: NodeId, nodes: Map<NodeId, FormulaNode>): List<NodeId> {
        require(root in nodes) { "Missing root: $root" }
        for ((id, node) in nodes.toSortedMap()) {
            require(id == node.id) { "Map key $id does not match node identity ${node.id}" }
            require(node !is LiteralNode || node.proposition.isNotBlank()) { "Empty proposition at $id" }
            for (child in node.children()) require(child in nodes) { "Missing child $child referenced by $id" }
        }
        val color = HashMap<NodeId, Int>()
        val postOrder = ArrayList<NodeId>()
        val stack = ArrayDeque<Pair<NodeId, Boolean>>()
        stack.addLast(root to false)
        while (stack.isNotEmpty()) {
            val (id, exiting) = stack.removeLast()
            if (exiting) {
                color[id] = 2
                postOrder.add(id)
            } else {
                when (color[id]) {
                    1 -> throw IllegalArgumentException("Cycle detected at $id")
                    2 -> continue
                }
                color[id] = 1
                stack.addLast(id to true)
                for (child in nodes.getValue(id).children().asReversed()) stack.addLast(child to false)
            }
        }
        require(postOrder.size == nodes.size) {
            "Unreachable nodes: ${(nodes.keys - color.keys).sorted().joinToString()}"
        }
        return immutableList(postOrder)
    }
}
