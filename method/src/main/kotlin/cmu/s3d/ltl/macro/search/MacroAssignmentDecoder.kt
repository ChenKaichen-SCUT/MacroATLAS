package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.*

data class AnchorAssignment(val label: Int, val state: Int)
data class PortAssignment(val target: Int, val fiber: Int)
data class MacroAssignment(
    val anchors: Map<Int, AnchorAssignment>, val ports: Map<String, PortAssignment>,
    val expandedSize: Int, val keptEdges: Int,
    val anchorValues: Set<Pair<Int, Int>>, val edgeValues: Set<Pair<String, Int>>
)
data class DecodedMacro<Q : Any>(val macro: MacroDag<Q>, val witness: FormulaDag, val slotIds: Map<Int, NodeId>)

object MacroAssignmentDecoder {
    fun <Q : Any> decode(context: MacroCompilationContext<Q>, assignment: MacroAssignment): DecodedMacro<Q> {
        val plan = context.plan
        val reserved = plan.protectedIdentities.map { it.id }.toMutableSet()
        fun fresh(base: String): NodeId {
            var id = NodeId(base); var suffix = 0
            while (!reserved.add(id)) id = NodeId("$base~${++suffix}")
            return id
        }
        val ids = assignment.anchors.keys.sorted().associateWith { i ->
            require(i in 0 until plan.anchorSlotBudget)
            plan.protectedIdentities.getOrNull(i)?.id ?: fresh("__search__/A$i")
        }
        val edges = linkedMapOf<MacroPort, CanonicalMacroEdge<Q>>()
        val heads = hashMapOf<MacroPort, NodeId>()
        for ((name, value) in assignment.ports.toSortedMap()) {
            val port = if (name == "R") MacroPort.ROOT else {
                val kind = when (name.first()) { 'C' -> PortKind.CHILD; 'L' -> PortKind.LEFT; 'D' -> PortKind.RIGHT; else -> error("Unknown port: $name") }
                MacroPort(ids.getValue(name.substring(1).toInt()), kind)
            }
            val entry = context.catalog.entries[value.fiber]
            val target = ids.getValue(value.target)
            val internalIds = entry.word.operators.indices.map { fresh("__witness__/$name/$it") }
            val raw = RawMacroEdge(port, target, entry.word, internalIds)
            edges[port] = CanonicalMacroEdge(raw, entry.key, entry.word)
            heads[port] = internalIds.firstOrNull() ?: target
        }
        val anchors = ids.mapValues { (i, id) ->
            when (val label = plan.labels[assignment.anchors.getValue(i).label]) {
                is MacroLabel.Literal -> LiteralNode(id, label.proposition)
                is MacroLabel.Unary -> UnaryNode(id, label.operator, heads.getValue(MacroPort(id, PortKind.CHILD)))
                is MacroLabel.Binary -> BinaryNode(id, label.operator, heads.getValue(MacroPort(id, PortKind.LEFT)), heads.getValue(MacroPort(id, PortKind.RIGHT)))
            }
        }.values.associateBy { it.id }
        val rootState = edges.getValue(MacroPort.ROOT).fiberKey.qOut
        // A certified root-unary profile deliberately keeps its otherwise
        // unshared outer operator as an anchor.  Mark it protected for the
        // canonical round-trip check; its identity is internal to this solve.
        val activeProtected = (ids.filterKeys { it < plan.protectedIdentities.size }.values +
            listOfNotNull(if (plan.requiredRootUnary != null) ids.getValue(assignment.ports.getValue("R").target) else null)).distinct()
        val macro = MacroDag(anchors, edges, activeProtected, assignment.expandedSize,
            rootState, plan.allowedUnaryOperators, plan.automaton)
        return DecodedMacro(macro, MacroDagExpander.expandOriginal(macro), ids)
    }
}
