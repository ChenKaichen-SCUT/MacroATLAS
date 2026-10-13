package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.constraint.ConstraintAutomaton
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Immutable fiber-labelled macro representation; contains no Alloy solution or solver reference. */
class MacroDag<Q : Any>(
    actualAnchors: Map<NodeId, FormulaNode>,
    edgesByPort: Map<MacroPort, CanonicalMacroEdge<Q>>,
    protectedNodeIds: Collection<NodeId>,
    val originalNodeCount: Int,
    val constraintRootState: Q,
    allowedUnaryOperators: Collection<UnaryOperator>,
    internal val automaton: ConstraintAutomaton<Q>
) {
    /** The external virtual root, never reconstructed as an LTL node. */
    val virtualRoot = VirtualRoot
    /** Original anchor descriptors; expansion rewires their ports but preserves IDs and labels. */
    val actualAnchors = immutableMap(actualAnchors.toSortedMap())
    /** Canonical edges in a deterministic full-port order. */
    val edgesByPort = immutableMap(edgesByPort.toSortedMap())
    /** Required actual identities, never eligible for absorption into edge interiors. */
    val protectedNodeIds = immutableSet(protectedNodeIds.sorted())
    /** Alphabet accepted during eligibility and used to generate the fiber table. */
    val allowedUnaryOperators = immutableList(allowedUnaryOperators.distinct().sortedBy { it.lexicalRank })
    /** Actual-anchor counts exclude VirtualRoot; canonical count includes only used unary nodes. */
    val statistics = kernelStatistics(
        this.actualAnchors, this.protectedNodeIds, this.edgesByPort.values.map { it.raw }, originalNodeCount,
        this.actualAnchors.size + this.edgesByPort.values.sumOf { it.representativeWord.length }
    )
}
