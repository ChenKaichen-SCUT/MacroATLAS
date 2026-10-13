package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.dag.NodeId
import cmu.s3d.ltl.macro.dag.immutableList
import cmu.s3d.ltl.macro.unary.UnaryWord

/** One maximal outer-to-inner unary path from a source port to an actual anchor. */
class RawMacroEdge(
    val port: MacroPort,
    val target: NodeId,
    val originalWord: UnaryWord,
    originalInternalNodeIds: Collection<NodeId>
) {
    /** Original identities parallel to originalWord, ordered outermost to innermost. */
    val originalInternalNodeIds: List<NodeId> = immutableList(originalInternalNodeIds)

    /** Exact edge equality, including the original syntax witness and identities. */
    override fun equals(other: Any?): Boolean = other is RawMacroEdge &&
        port == other.port && target == other.target && originalWord == other.originalWord &&
        originalInternalNodeIds == other.originalInternalNodeIds

    /** Content hash of the immutable edge. */
    override fun hashCode(): Int = listOf(port, target, originalWord, originalInternalNodeIds).hashCode()

    /** Finite path description for debug reports. */
    override fun toString(): String = "$port --[$originalWord]--> $target ($originalInternalNodeIds)"
}
