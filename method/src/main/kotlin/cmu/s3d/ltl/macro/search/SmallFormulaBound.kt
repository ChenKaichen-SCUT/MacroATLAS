package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.dag.*

/**
 * Proves an optimum of one or two nodes before invoking MaxSAT.  This is a
 * complete enumeration of that tiny anonymous fragment: a literal, a unary
 * operation on one literal, or a binary operation whose two ports share one
 * literal.  Plans with named identities or extra identity constraints use the
 * general encoding instead.
 */
object SmallFormulaBound {
    fun <Q : Any> optimum(context: MacroCompilationContext<Q>): Int? {
        val plan = context.plan
        if (plan.objective !is MacroObjective.MinExpandedSize ||
            plan.protectedIdentities.isNotEmpty() || plan.identityConstraints.isNotEmpty()) return null
        val positives = context.originalPositives
        val negatives = context.originalNegatives
        fun matches(dag: FormulaDag): Boolean =
            positives.all { ConcreteLassoEvaluator.values(dag, it).getValue(dag.root)[0] } &&
                negatives.none { ConcreteLassoEvaluator.values(dag, it).getValue(dag.root)[0] }
        val root = NodeId("__small__/root")
        val leaf = NodeId("__small__/leaf")
        for (proposition in plan.propositions) {
            val state = plan.automaton.literalState(proposition)
            if (plan.automaton.isAccepting(state) && matches(FormulaDag(root, listOf(LiteralNode(root, proposition)))))
                return 1
        }
        if (plan.nodeBudget < 2) return null
        for (proposition in plan.propositions) {
            val state = plan.automaton.literalState(proposition)
            val literal = LiteralNode(leaf, proposition)
            for (operator in plan.allowedUnaryOperators) {
                if (!plan.automaton.isAccepting(plan.automaton.unaryState(operator, state))) continue
                val dag = FormulaDag(root, listOf(UnaryNode(root, operator, leaf), literal))
                if (matches(dag)) return 2
            }
            if (plan.binaryBudget > 0) for (operator in plan.allowedBinaryOperators) {
                if (operator == BinaryOperator.UNTIL ||
                    !plan.automaton.isAccepting(plan.automaton.binaryState(operator, state, state))) continue
                val dag = FormulaDag(root, listOf(BinaryNode(root, operator, leaf, leaf), literal))
                if (matches(dag)) return 2
            }
        }
        return null
    }
}
