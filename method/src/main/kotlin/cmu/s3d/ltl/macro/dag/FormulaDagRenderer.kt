package cmu.s3d.ltl.macro.dag

/** Display-only tree expansion matching ATLAS getLTL2(); never used to recover identity. */
object FormulaDagRenderer {
    /** Render deterministically using a memoized, iterative bottom-up traversal. */
    fun render(dag: FormulaDag): String {
        val rendered = HashMap<NodeId, String>()
        for (id in dag.postOrder()) rendered[id] = when (val node = dag.node(id)) {
            is LiteralNode -> node.proposition
            is UnaryNode -> "${node.operator.symbol}(${rendered.getValue(node.child)})"
            is BinaryNode -> "${node.operator.symbol}(${rendered.getValue(node.left)},${rendered.getValue(node.right)})"
        }
        return rendered.getValue(dag.root)
    }
}
