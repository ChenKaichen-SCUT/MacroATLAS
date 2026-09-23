package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.PortKind
import cmu.s3d.ltl.macro.unary.UnaryOperator

enum class MacroSolverMode { OFF, AUTO, FORCE }
enum class MacroUnsupportedReason {
    BINARY_TEMPORAL_UNTIL_REQUIRED, UNKNOWN_CUSTOM_ALLOY_CONSTRAINT,
    UNSUPPORTED_OBJECTIVE, PROTECTED_IDENTITY_NOT_RESOLVABLE, BINARY_BUDGET_MISSING,
    INVALID_BUDGET, INVALID_TRACE, UNSUPPORTED_BACKEND
}

sealed class MacroLabel {
    data class Literal(val proposition: String) : MacroLabel()
    data class Unary(val operator: UnaryOperator) : MacroLabel()
    data class Binary(val operator: BinaryOperator) : MacroLabel()
}
data class ProtectedIdentity(val id: NodeId, val label: MacroLabel)
data class ProtectedEdge(val source: NodeId, val target: NodeId)
sealed class MacroIdentityConstraint {
    data class NoDAGReuse(val excludeLiterals: Boolean = false) : MacroIdentityConstraint()
    object NoSharedLiteralBranches : MacroIdentityConstraint()
    object LeftNotEqualRight : MacroIdentityConstraint()
    data class NamedDirectChild(val source: NodeId, val port: PortKind, val target: NodeId) : MacroIdentityConstraint()
    data class NamedReachability(val source: NodeId, val target: NodeId) : MacroIdentityConstraint()
    data class NamedRoot(val target: NodeId) : MacroIdentityConstraint()
}
sealed class MacroObjective {
    object MinExpandedSize : MacroObjective()
    class Repair(edges: Collection<ProtectedEdge>) : MacroObjective() {
        val oldEdges = immutableSet(edges)
    }
}

/** Trusted, fully understood input to the compiler. Raw Alloy is deliberately absent. */
class MacroConstraintPlan<Q : Any>(
    val automaton: ConstraintAutomaton<Q>, propositions: Collection<String>,
    val nodeBudget: Int, val binaryBudget: Int,
    allowedUnaryOperators: Collection<UnaryOperator> = UnaryOperator.LEXICAL_ORDER,
    allowedBinaryOperators: Collection<BinaryOperator> = listOf(BinaryOperator.AND, BinaryOperator.OR, BinaryOperator.IMPLIES),
    protectedIdentities: Collection<ProtectedIdentity> = emptyList(),
    identityConstraints: Collection<MacroIdentityConstraint> = emptyList(),
    val objective: MacroObjective = MacroObjective.MinExpandedSize,
    val uniqueLiteralIdentities: Boolean = false,
    requiredProtectedIdentities: Collection<NodeId> = protectedIdentities.map { it.id }
) {
    val propositions = immutableList(propositions.distinct().sorted())
    val allowedUnaryOperators = immutableList(allowedUnaryOperators.distinct().sortedBy { it.lexicalRank })
    val allowedBinaryOperators = immutableList(allowedBinaryOperators.distinct().sortedBy { it.ordinal })
    val protectedIdentities = immutableList(protectedIdentities.sortedBy { it.id })
    val requiredProtectedIdentities = immutableSet(requiredProtectedIdentities.sorted())
    val identityConstraints = immutableList(identityConstraints)
    val anchorSlotBudget: Int = minOf(nodeBudget.toLong(), protectedIdentities.size + 3L * binaryBudget + 2).toInt()
    val labels: List<MacroLabel> = immutableList(this.propositions.map { MacroLabel.Literal(it) } +
        this.allowedUnaryOperators.map { MacroLabel.Unary(it) } + this.allowedBinaryOperators.map { MacroLabel.Binary(it) })
    init {
        require(nodeBudget >= 1 && binaryBudget >= 0)
        require(this.propositions.isNotEmpty())
        require(BinaryOperator.UNTIL !in this.allowedBinaryOperators)
        require(this.protectedIdentities.map { it.id }.distinct().size == this.protectedIdentities.size)
        require(this.requiredProtectedIdentities.all { required -> this.protectedIdentities.any { it.id == required } })
        require(this.protectedIdentities.all { it.label in labels })
        val ids = this.protectedIdentities.map { it.id }.toSet()
        for (c in this.identityConstraints) when (c) {
            is MacroIdentityConstraint.NamedDirectChild -> {
                require(c.source in ids && c.target in ids)
                val label = this.protectedIdentities.single { it.id == c.source }.label
                require((label is MacroLabel.Unary && c.port == PortKind.CHILD) ||
                    (label is MacroLabel.Binary && c.port in listOf(PortKind.LEFT, PortKind.RIGHT)))
            }
            is MacroIdentityConstraint.NamedReachability -> require(c.source in ids && c.target in ids)
            is MacroIdentityConstraint.NamedRoot -> require(c.target in ids)
            else -> Unit
        }
        if (objective is MacroObjective.Repair) require(objective.oldEdges.all { it.source in ids && it.target in ids })
    }
}

sealed class MacroTaskAnalysis {
    data class Supported(val plan: MacroConstraintPlan<*>, val recognizedFeatures: List<String>) : MacroTaskAnalysis()
    data class Unsupported(val reasons: List<MacroUnsupportedReason>, val detail: String) : MacroTaskAnalysis()
}
