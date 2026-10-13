package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Exact outer shape G(_ -> F(_)); unlike [FixedTemplateAutomaton], children may be temporal. */
class ResponseOuterShapeAutomaton : ConstraintAutomaton<ResponseOuterShapeAutomaton.State> {
    enum class State { OTHER, F_ROOT, IMPLY_WITH_F_RIGHT, ACCEPT }

    override fun literalState(proposition: String) = State.OTHER

    override fun unaryState(operator: UnaryOperator, child: State): State = when {
        operator == UnaryOperator.F -> State.F_ROOT
        operator == UnaryOperator.G && child == State.IMPLY_WITH_F_RIGHT -> State.ACCEPT
        else -> State.OTHER
    }

    override fun binaryState(operator: BinaryOperator, left: State, right: State): State =
        if (operator == BinaryOperator.IMPLIES && right == State.F_ROOT) State.IMPLY_WITH_F_RIGHT else State.OTHER

    override fun isAccepting(state: State) = state == State.ACCEPT
}

/**
 * Exact regular-tree interpretation of the two weakening templates in the paper artifact.
 * It recognizes G(Imply0), the local CNF/DNF restrictions below every implication, and
 * the named endpoint alternatives. Names themselves are immaterial because no repair
 * objective refers to them in these tasks.
 */
class WeakeningTemplateAutomaton(private val consequent: Boolean) : ConstraintAutomaton<WeakeningTemplateAutomaton.State> {
    enum class Label { X0, X1, X2, OTHER_LITERAL, NEG, AND, OR, IMPLY, G, OTHER }

    data class State(
        val label: Label,
        val body: Boolean = false,
        val containsAnd: Boolean = false,
        val containsOr: Boolean = false,
        val noAndBelowOr: Boolean = false,
        val noOrBelowAnd: Boolean = false,
        val leftAlternative: Boolean = false,
        val rightX1Alternative: Boolean = false,
        val rightAnd12Alternative: Boolean = false,
        val exactAnd12: Boolean = false,
        val antecedentImplication: Boolean = false,
        val consequentImplication: Boolean = false,
        val acceptedAntecedent: Boolean = false,
        val acceptedConsequent: Boolean = false
    )

    private fun literal(label: Label) = State(label, body = true, noAndBelowOr = true, noOrBelowAnd = true,
        leftAlternative = label == Label.X0, rightX1Alternative = label == Label.X1)

    override fun literalState(proposition: String): State = literal(when (proposition) {
        "x0" -> Label.X0
        "x1" -> Label.X1
        "x2" -> Label.X2
        else -> Label.OTHER_LITERAL
    })

    override fun unaryState(operator: UnaryOperator, child: State): State = when {
        operator == UnaryOperator.NOT && child.label in setOf(Label.X0, Label.X1, Label.X2, Label.OTHER_LITERAL) ->
            State(Label.NEG, body = true, noAndBelowOr = true, noOrBelowAnd = true)
        operator == UnaryOperator.G -> State(Label.G,
            acceptedAntecedent = child.antecedentImplication,
            acceptedConsequent = child.consequentImplication)
        else -> State(Label.OTHER)
    }

    override fun binaryState(operator: BinaryOperator, left: State, right: State): State {
        if (operator == BinaryOperator.AND || operator == BinaryOperator.OR) {
            val and = operator == BinaryOperator.AND
            val body = left.body && right.body
            val exactAnd12 = and && ((left.label == Label.X1 && right.label == Label.X2) ||
                (left.label == Label.X2 && right.label == Label.X1))
            return State(
                if (and) Label.AND else Label.OR,
                body = body,
                containsAnd = and || left.containsAnd || right.containsAnd,
                containsOr = !and || left.containsOr || right.containsOr,
                noAndBelowOr = body && left.noAndBelowOr && right.noAndBelowOr &&
                    (and || (!left.containsAnd && !right.containsAnd)),
                noOrBelowAnd = body && left.noOrBelowAnd && right.noOrBelowAnd &&
                    (!and || (!left.containsOr && !right.containsOr)),
                leftAlternative = and && left.label == Label.X0,
                rightX1Alternative = !and && left.label == Label.X1,
                rightAnd12Alternative = !and && left.exactAnd12,
                exactAnd12 = exactAnd12
            )
        }
        if (operator == BinaryOperator.IMPLIES) {
            val common = left.body && right.body && left.noAndBelowOr && right.noOrBelowAnd
            val leftOk = left.label == Label.X0 || left.leftAlternative
            val antecedent = common && leftOk && (right.label == Label.X1 || right.rightX1Alternative)
            val consequent = common && leftOk && (right.exactAnd12 || right.rightAnd12Alternative)
            return State(Label.IMPLY, antecedentImplication = antecedent, consequentImplication = consequent)
        }
        return State(Label.OTHER)
    }

    override fun isAccepting(state: State): Boolean =
        if (consequent) state.acceptedConsequent else state.acceptedAntecedent
}
