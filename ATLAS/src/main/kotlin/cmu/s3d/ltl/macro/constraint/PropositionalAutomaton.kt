package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Accept subtrees containing none of X, F, G, U. */
class PropositionalAutomaton : ConstraintAutomaton<PropositionalAutomaton.State> {
    /** Whether a temporal operator occurs anywhere in the subtree. */
    enum class State { PROP, NON_PROP }

    /** Every atom is propositional. */
    override fun literalState(proposition: String): State = State.PROP

    /** Negation preserves the child classification; temporal unary operators do not. */
    override fun unaryState(operator: UnaryOperator, child: State): State =
        if (operator == UnaryOperator.NOT) child else State.NON_PROP

    /** Boolean operators require propositional children; U is explicitly temporal. */
    override fun binaryState(operator: BinaryOperator, left: State, right: State): State =
        if (operator != BinaryOperator.UNTIL && left == State.PROP && right == State.PROP)
            State.PROP else State.NON_PROP

    /** Accept exactly propositional subtrees. */
    override fun isAccepting(state: State): Boolean = state == State.PROP
}
