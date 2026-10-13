package cmu.s3d.ltl.macro.fiber

import cmu.s3d.ltl.macro.unary.SemanticType

/**
 * Safe unary quotient key: child state, semantic context, syntax nonemptiness, and
 * output state. Neither the constraint profile nor nonEmpty may be discarded.
 * Q must satisfy ConstraintAutomaton's immutable equality/hashCode contract.
 */
data class FiberKey<Q : Any>(
    val qIn: Q,
    val semanticType: SemanticType,
    val nonEmpty: Boolean,
    val qOut: Q
)
