package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Accept when the exact ATLAS proposition name [target] occurs in the subtree. */
class RequiredPropositionAutomaton(val target: String) : ConstraintAutomaton<RequiredPropositionAutomaton.State> {
    /** Presence of the designated proposition; independent of its truth value. */
    enum class State { ABSENT, PRESENT }

    /** Compare the same String identities used in Task.literals, without renaming. */
    override fun literalState(proposition: String): State =
        if (proposition == target) State.PRESENT else State.ABSENT

    /** Unary operators cannot add or remove proposition occurrences. */
    override fun unaryState(operator: UnaryOperator, child: State): State = child

    /** An occurrence in either child suffices, for every ATLAS binary operator. */
    override fun binaryState(operator: BinaryOperator, left: State, right: State): State =
        if (left == State.PRESENT || right == State.PRESENT) State.PRESENT else State.ABSENT

    /** Accept exactly subtrees containing the target. */
    override fun isAccepting(state: State): Boolean = state == State.PRESENT
}
