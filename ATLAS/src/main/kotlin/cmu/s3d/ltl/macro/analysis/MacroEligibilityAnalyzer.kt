package cmu.s3d.ltl.macro.analysis

import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.constraint.ConstraintAutomaton
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Checks the U-free, explicitly supplied constraint envelope; does not parse Alloy text. */
class MacroEligibilityAnalyzer<Q : Any>(private val automaton: ConstraintAutomaton<Q>) {
    /**
     * Analyze the supplied profile. Pass Task.customConstraints as unhandledAlloyConstraints
     * when no external recognized-profile compiler has accounted for it. Nonblank raw
     * text is always rejected, even if every node is protected: exact lengths/counts
     * and arbitrary relational objectives cannot be inferred from a protected set.
     * Omitting text asserts that the supplied automaton/protected set is the full scope.
     */
    fun analyze(
        dag: FormulaDag,
        protectedNodeIds: Collection<NodeId> = emptySet(),
        allowedUnaryOperators: Collection<UnaryOperator> = UnaryOperator.LEXICAL_ORDER,
        unhandledAlloyConstraints: String? = null
    ): MacroEligibility<Q> {
        val reasons = ArrayList<MacroEligibility.Reason>()
        try {
            FormulaDagValidator.validate(dag)
        } catch (e: IllegalArgumentException) {
            reasons.add(MacroEligibility.Reason(MacroEligibility.Code.INVALID_STRUCTURE, e.message ?: "Invalid DAG"))
        }
        for ((id, node) in dag.nodes) {
            if (node is BinaryNode && node.operator == BinaryOperator.UNTIL)
                reasons.add(MacroEligibility.Reason(MacroEligibility.Code.UNTIL, "Binary U is outside the macro fragment", id))
            if (node is UnaryNode && node.operator !in allowedUnaryOperators)
                reasons.add(MacroEligibility.Reason(MacroEligibility.Code.DISALLOWED_UNARY, "Unary ${node.operator.symbol} is not allowed", id))
        }
        for (id in protectedNodeIds.distinct().sorted()) if (id !in dag.nodes)
            reasons.add(MacroEligibility.Reason(MacroEligibility.Code.UNKNOWN_PROTECTED_NODE, "Unknown protected identity $id", id))
        if (!unhandledAlloyConstraints.isNullOrBlank())
            reasons.add(MacroEligibility.Reason(MacroEligibility.Code.UNHANDLED_ALLOY_CONSTRAINTS, "Raw Alloy constraints have not been compiled into a supported profile"))
        if (reasons.isNotEmpty()) return MacroEligibility.Unsupported(reasons)
        val evaluation = try {
            DagConstraintEvaluator(automaton).evaluate(dag).also { automaton.isAccepting(it.rootState) }
        } catch (e: Exception) {
            return MacroEligibility.Unsupported(listOf(MacroEligibility.Reason(
                MacroEligibility.Code.AUTOMATON_EVALUATION_FAILED,
                "${e.javaClass.simpleName}: ${e.message ?: "Automaton is not total on this DAG"}"
            )))
        }
        return MacroEligibility.Eligible(dag, automaton, evaluation, protectedNodeIds, allowedUnaryOperators)
    }
}
