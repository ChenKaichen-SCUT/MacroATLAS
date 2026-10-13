package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.dag.*

/** A virtual source outside FormulaDag's identity domain, with no LTL operator. */
object VirtualRoot

/** Explicit port order used throughout decomposition and deterministic reconstruction. */
enum class PortKind { ROOT, CHILD, LEFT, RIGHT }

/** A port's full identity includes its source; null is reserved exclusively for VirtualRoot. */
data class MacroPort(val source: NodeId?, val kind: PortKind) : Comparable<MacroPort> {
    init { require((source == null) == (kind == PortKind.ROOT)) { "Only VirtualRoot has a ROOT port" } }

    /** Virtual root first, then source NodeId and the explicit CHILD/LEFT/RIGHT order. */
    override fun compareTo(other: MacroPort): Int {
        if (source == null) return if (other.source == null) 0 else -1
        if (other.source == null) return 1
        val sourceOrder = source.compareTo(other.source)
        return if (sourceOrder == 0) kind.ordinal.compareTo(other.kind.ordinal) else sourceOrder
    }

    companion object {
        /** The sole virtual-root port. */
        val ROOT = MacroPort(null, PortKind.ROOT)
    }
}

internal fun portsOf(anchors: Map<NodeId, FormulaNode>): List<MacroPort> {
    val ports = arrayListOf(MacroPort.ROOT)
    for ((id, node) in anchors.toSortedMap()) when (node) {
        is LiteralNode -> Unit
        is UnaryNode -> ports.add(MacroPort(id, PortKind.CHILD))
        is BinaryNode -> {
            ports.add(MacroPort(id, PortKind.LEFT))
            ports.add(MacroPort(id, PortKind.RIGHT))
        }
    }
    return immutableList(ports)
}

internal fun immediateChild(dag: FormulaDag, port: MacroPort): NodeId = when (port.kind) {
    PortKind.ROOT -> dag.root
    PortKind.CHILD -> (dag.node(requireNotNull(port.source)) as UnaryNode).child
    PortKind.LEFT -> (dag.node(requireNotNull(port.source)) as BinaryNode).left
    PortKind.RIGHT -> (dag.node(requireNotNull(port.source)) as BinaryNode).right
}
