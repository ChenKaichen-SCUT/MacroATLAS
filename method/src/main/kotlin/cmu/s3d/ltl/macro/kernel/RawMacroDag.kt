package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.analysis.MacroEligibility
import cmu.s3d.ltl.macro.dag.*

/** Immutable anchor decomposition of an eligible DAG, before representative selection. */
class RawMacroDag<Q : Any> internal constructor(
    internal val eligibility: MacroEligibility.Eligible<Q>,
    actualAnchors: Map<NodeId, FormulaNode>,
    edgesByPort: Map<MacroPort, RawMacroEdge>
) {
    /** Virtual source is not an actual formula node. */
    val virtualRoot = VirtualRoot
    /** Original immutable formula snapshot. */
    val originalDag = eligibility.dag
    /** Original per-node constraint evaluation, including the full root state. */
    val evaluation = eligibility.evaluation
    /** Actual anchors retain original identities, labels and outgoing references. */
    val actualAnchors = immutableMap(actualAnchors.toSortedMap())
    /** Exactly one maximal unary path per port. */
    val edgesByPort = immutableMap(edgesByPort.toSortedMap())
    /** Caller-supplied protected identities. */
    val protectedNodeIds = eligibility.protectedNodeIds
    /** Checked unary alphabet carried from eligibility. */
    val allowedUnaryOperators = eligibility.allowedUnaryOperators
    /** Before canonicalization both node counts refer to the original graph. */
    val statistics = kernelStatistics(this.actualAnchors, protectedNodeIds, this.edgesByPort.values, originalDag.size(), originalDag.size())
}
