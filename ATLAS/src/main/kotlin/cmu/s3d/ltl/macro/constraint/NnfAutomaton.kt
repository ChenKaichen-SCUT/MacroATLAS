package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** ATLAS-style NNF: negation may occur only immediately above an atomic proposition. */
class NnfAutomaton : ConstraintAutomaton<NnfAutomaton.State> {
    /** Distinguish atoms from other valid subtrees so !!p is rejected. */
    enum class State { ATOM, VALID_NON_ATOM, INVALID }

    /** An atom is a valid target for negation. */
    override fun literalState(proposition: String): State = State.ATOM

    /** Reject negation of every non-atom and propagate invalid descendants. */
    override fun unaryState(operator: UnaryOperator, child: State): State = when {
        child == State.INVALID -> State.INVALID
        operator == UnaryOperator.NOT && child != State.ATOM -> State.INVALID
        else -> State.VALID_NON_ATOM
    }

    /** All ATLAS binary operators, including implication and U, preserve valid NNF children. */
    override fun binaryState(operator: BinaryOperator, left: State, right: State): State =
        if (left == State.INVALID || right == State.INVALID) State.INVALID else State.VALID_NON_ATOM

    /** Accept both atoms and valid compound subtrees. */
    override fun isAccepting(state: State): Boolean = state != State.INVALID
}
