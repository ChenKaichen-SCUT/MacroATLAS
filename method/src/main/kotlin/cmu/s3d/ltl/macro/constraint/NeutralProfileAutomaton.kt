package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/** RQ4-only profile stressor. Its state records X-depth modulo [modulus],
 * but every state accepts, so it changes no formula's feasibility. Do not
 * minimize this component in the RQ4 path: ordinary language minimization
 * correctly collapses all of its states into one.
 */
class NeutralProfileAutomaton(val modulus: Int) : ConstraintAutomaton<Int> {
    init { require(modulus in listOf(1, 2, 4, 8, 16)) }

    override fun literalState(proposition: String): Int = 0
    override fun unaryState(operator: UnaryOperator, child: Int): Int {
        require(child in 0 until modulus)
        return if (operator == UnaryOperator.X) (child + 1) % modulus else child
    }
    override fun binaryState(operator: BinaryOperator, left: Int, right: Int): Int {
        require(left in 0 until modulus && right in 0 until modulus)
        return (left + right + 1) % modulus
    }
    override fun isAccepting(state: Int): Boolean {
        require(state in 0 until modulus)
        return true
    }
}
