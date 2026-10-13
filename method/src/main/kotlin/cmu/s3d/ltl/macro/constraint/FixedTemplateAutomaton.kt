package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Recognizes syntactic G(Prop) or G(Prop -> F(Prop)); Prop allows arbitrary Boolean connectives. */
class FixedTemplateAutomaton(val response: Boolean = false) : ConstraintAutomaton<FixedTemplateAutomaton.State> {
    enum class State { PROP, F_PROP, RESPONSE, ACCEPT, OTHER }
    override fun literalState(proposition: String) = State.PROP
    override fun unaryState(operator: UnaryOperator, child: State): State = when {
        operator == UnaryOperator.NOT && child == State.PROP -> State.PROP
        operator == UnaryOperator.F && child == State.PROP -> State.F_PROP
        operator == UnaryOperator.G && child == (if (response) State.RESPONSE else State.PROP) -> State.ACCEPT
        else -> State.OTHER
    }
    override fun binaryState(operator: BinaryOperator, left: State, right: State): State = when {
        operator != BinaryOperator.UNTIL && left == State.PROP && right == State.PROP -> State.PROP
        operator == BinaryOperator.IMPLIES && left == State.PROP && right == State.F_PROP -> State.RESPONSE
        else -> State.OTHER
    }
    override fun isAccepting(state: State) = state == State.ACCEPT
}

/** Root label is observable even when its unary node is inside the virtual-root fiber. */
class RootOperatorAutomaton(private val required: String) : ConstraintAutomaton<String> {
    override fun literalState(proposition: String) = "Literal"
    override fun unaryState(operator: UnaryOperator, child: String) = operator.atlasName
    override fun binaryState(operator: BinaryOperator, left: String, right: String) = operator.atlasName
    override fun isAccepting(state: String) = state == required
}
