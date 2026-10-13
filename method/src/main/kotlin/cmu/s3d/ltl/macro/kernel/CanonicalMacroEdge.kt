package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.dag.NodeId
import cmu.s3d.ltl.macro.fiber.FiberKey
import cmu.s3d.ltl.macro.unary.UnaryWord

/** Full constraint-preserving fiber and its shortest deterministic syntax representative. */
data class CanonicalMacroEdge<Q : Any>(
    val raw: RawMacroEdge,
    val fiberKey: FiberKey<Q>,
    val representativeWord: UnaryWord
) {
    /** Source identity (null for VirtualRoot). */
    val source: NodeId? get() = raw.port.source
    /** Ordered source port. */
    val port: MacroPort get() = raw.port
    /** Unchanged actual target anchor identity. */
    val target: NodeId get() = raw.target
    /** Original outer-to-inner syntax word. */
    val originalWord: UnaryWord get() = raw.originalWord
    /** Original unprotected internal identities used only by original expansion. */
    val originalInternalNodeIds: List<NodeId> get() = raw.originalInternalNodeIds
}
