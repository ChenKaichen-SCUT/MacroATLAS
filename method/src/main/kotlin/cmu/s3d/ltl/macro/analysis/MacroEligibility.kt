package cmu.s3d.ltl.macro.analysis

import cmu.s3d.ltl.macro.constraint.ConstraintAutomaton
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Structured boundary between supported automaton/protected-node profiles and unsupported input. */
sealed class MacroEligibility<out Q : Any> {
    /** Validated input; the same automaton instance is carried through the complete pipeline. */
    class Eligible<Q : Any> internal constructor(
        val dag: FormulaDag,
        internal val automaton: ConstraintAutomaton<Q>,
        val evaluation: DagConstraintEvaluation<Q>,
        protectedNodeIds: Collection<NodeId>,
        allowedUnaryOperators: Collection<UnaryOperator>
    ) : MacroEligibility<Q>() {
        /** Exact protected identities, never interpreted as labels. */
        val protectedNodeIds: Set<NodeId> = immutableSet(protectedNodeIds.sorted())
        /** Unique allowed alphabet in Phase 1's fixed order. */
        val allowedUnaryOperators: List<UnaryOperator> = immutableList(allowedUnaryOperators.distinct().sortedBy { it.lexicalRank })
    }

    /** Explicit rejection; no silent fallback or partial normalization occurs. */
    class Unsupported(reasons: Collection<Reason>) : MacroEligibility<Nothing>() {
        /** Immutable deterministic explanations of unsupported features. */
        val reasons: List<Reason> = immutableList(reasons)
    }

    /** Machine-readable unsupported category. */
    enum class Code {
        INVALID_STRUCTURE, UNTIL, DISALLOWED_UNARY, UNKNOWN_PROTECTED_NODE,
        UNHANDLED_ALLOY_CONSTRAINTS, AUTOMATON_EVALUATION_FAILED
    }

    /** One actionable reason, optionally tied to an exact node identity. */
    data class Reason(val code: Code, val message: String, val nodeId: NodeId? = null)
}

/** Raised when extraction is attempted on an explicitly unsupported eligibility result. */
class MacroIneligibleException(reasons: Collection<MacroEligibility.Reason>) :
    IllegalArgumentException(reasons.joinToString { "${it.code}: ${it.message}" }) {
    /** The same structured diagnostics returned by the analyzer. */
    val reasons: List<MacroEligibility.Reason> = immutableList(reasons)
}
