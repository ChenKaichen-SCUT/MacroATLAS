package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Propositional CNF over atom, !, |, &: no conjunction may occur beneath a disjunction. */
class CnfAutomaton : ConstraintAutomaton<CnfAutomaton.State> {
    /** CNF records that an AND occurs; CLAUSE is a non-atomic subtree without AND. */
    enum class State { ATOM, CLAUSE, CNF, INVALID }

    /** Atoms are clauses and valid CNF, but remain distinguishable for negation. */
    override fun literalState(proposition: String): State = State.ATOM

    /** Only a single negation directly on an atom is legal. */
    override fun unaryState(operator: UnaryOperator, child: State): State =
        if (operator == UnaryOperator.NOT && child == State.ATOM) State.CLAUSE else State.INVALID

    /** Conjoin any valid CNFs; disjoin only atom/clause children. */
    override fun binaryState(operator: BinaryOperator, left: State, right: State): State = when {
        left == State.INVALID || right == State.INVALID -> State.INVALID
        operator == BinaryOperator.AND -> State.CNF
        operator == BinaryOperator.OR && left != State.CNF && right != State.CNF -> State.CLAUSE
        else -> State.INVALID
    }

    /** Accept atoms, clauses, and conjunctions of clauses. */
    override fun isAccepting(state: State): Boolean = state != State.INVALID
}
