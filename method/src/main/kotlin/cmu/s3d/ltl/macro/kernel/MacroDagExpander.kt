package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryWord

/** Deterministic original-identity reconstruction and fresh-identity canonical expansion. */
object MacroDagExpander {
    /** Reconstruct an unlabelled decomposition exactly, including all original IDs and sharing. */
    fun expandOriginal(raw: RawMacroDag<*>): FormulaDag = expand(raw.actualAnchors, raw.edgesByPort, null)

    /** Reconstruct the original formula recorded in a fiber-labelled macro DAG. */
    fun expandOriginal(macro: MacroDag<*>): FormulaDag = expand(macro.actualAnchors, macro.edgesByPort.mapValues { it.value.raw }, null)

    /** Expand shortest words, retaining all actual anchors and allocating fresh internal IDs. */
    fun expandCanonical(macro: MacroDag<*>): FormulaDag = expand(
        macro.actualAnchors, macro.edgesByPort.mapValues { it.value.raw },
        macro.edgesByPort.mapValues { it.value.representativeWord }
    )

    private fun expand(
        anchors: Map<NodeId, FormulaNode>, edges: Map<MacroPort, RawMacroEdge>,
        representatives: Map<MacroPort, UnaryWord>?
    ): FormulaDag {
        require(edges.keys == portsOf(anchors).toSet()) { "Missing or extra macro ports" }
        val nodes = LinkedHashMap<NodeId, FormulaNode>()
        nodes.putAll(anchors)
        val reserved = (anchors.keys + edges.values.flatMap { it.originalInternalNodeIds }).toMutableSet()
        val heads = HashMap<MacroPort, NodeId>()
        for ((port, edge) in edges.toSortedMap()) {
            require(port == edge.port) { "Edge stored at the wrong port: $port" }
            require(edge.target in anchors) { "Edge target is not an anchor: ${edge.target}" }
            require(edge.originalWord.length == edge.originalInternalNodeIds.size) { "Original word/identity length mismatch" }
            val word = representatives?.getValue(port) ?: edge.originalWord
            val ids = if (representatives == null) edge.originalInternalNodeIds else word.operators.indices.map { position ->
                val source = port.source?.value?.let { "node${it.length}:$it" } ?: "virtual"
                val base = "__macro__/$source/${port.kind.name}/$position"
                var candidate = NodeId(base)
                var suffix = 0
                while (candidate in reserved) candidate = NodeId("$base~${++suffix}")
                reserved.add(candidate)
                candidate
            }
            var child = edge.target
            for (i in word.length - 1 downTo 0) {
                val id = ids[i]
                require(id !in nodes) { "Duplicate internal/anchor identity: $id" }
                nodes[id] = UnaryNode(id, word.operators[i], child)
                child = id
            }
            heads[port] = child
        }
        for ((id, node) in anchors) nodes[id] = when (node) {
            is LiteralNode -> node
            is UnaryNode -> node.copy(child = heads.getValue(MacroPort(id, PortKind.CHILD)))
            is BinaryNode -> node.copy(left = heads.getValue(MacroPort(id, PortKind.LEFT)), right = heads.getValue(MacroPort(id, PortKind.RIGHT)))
        }
        return FormulaDag(heads.getValue(MacroPort.ROOT), nodes)
    }
}
