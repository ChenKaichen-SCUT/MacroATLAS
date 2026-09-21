package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/**
 * Deterministic bottom-up constraint automaton. States must be immutable values with
 * stable equality/hashCode, and transitions must be total on the automaton's states.
 * Propositions reuse ATLAS's String identity (Task.literals and State.values keys).
 */
interface ConstraintAutomaton<S : Any> {
    /** State of an atomic proposition with its original ATLAS name. */
    fun literalState(proposition: String): S

    /** State of operator(child). */
    fun unaryState(operator: UnaryOperator, child: S): S

    /** State of operator(left, right), including ATLAS's binary Until operator. */
    fun binaryState(operator: BinaryOperator, left: S, right: S): S

    /** Whether this complete subtree satisfies the constraint. */
    fun isAccepting(state: S): Boolean
}
