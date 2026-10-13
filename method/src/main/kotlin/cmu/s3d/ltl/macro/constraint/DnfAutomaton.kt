package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Propositional DNF, dual to CNF: no disjunction may occur beneath a conjunction. */
class DnfAutomaton : ConstraintAutomaton<DnfAutomaton.State> {
    /** DNF records that an OR occurs; TERM is a non-atomic subtree without OR. */
    enum class State { ATOM, TERM, DNF, INVALID }

    /** Atoms are terms and valid DNF, but remain distinguishable for negation. */
    override fun literalState(proposition: String): State = State.ATOM

    /** Only a single negation directly on an atom is legal. */
    override fun unaryState(operator: UnaryOperator, child: State): State =
        if (operator == UnaryOperator.NOT && child == State.ATOM) State.TERM else State.INVALID

    /** Disjoin any valid DNFs; conjoin only atom/term children. */
    override fun binaryState(operator: BinaryOperator, left: State, right: State): State = when {
        left == State.INVALID || right == State.INVALID -> State.INVALID
        operator == BinaryOperator.OR -> State.DNF
        operator == BinaryOperator.AND && left != State.DNF && right != State.DNF -> State.TERM
        else -> State.INVALID
    }

    /** Accept atoms, terms, and disjunctions of terms. */
    override fun isAccepting(state: State): Boolean = state != State.INVALID
}
