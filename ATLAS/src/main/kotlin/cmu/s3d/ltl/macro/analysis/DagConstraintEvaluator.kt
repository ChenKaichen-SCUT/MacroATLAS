package cmu.s3d.ltl.macro.analysis

import cmu.s3d.ltl.macro.constraint.ConstraintAutomaton
import cmu.s3d.ltl.macro.dag.*

/** Bridge from an immutable DAG to the existing Phase 1 automaton API. */
class DagConstraintEvaluator<Q : Any>(private val automaton: ConstraintAutomaton<Q>) {
    /** Evaluate each actual node once, in postorder, without filtering nonaccepting subtrees. */
    fun evaluate(dag: FormulaDag): DagConstraintEvaluation<Q> {
        val states = LinkedHashMap<NodeId, Q>()
        for (id in dag.postOrder()) states[id] = when (val node = dag.node(id)) {
            is LiteralNode -> automaton.literalState(node.proposition)
            is UnaryNode -> automaton.unaryState(node.operator, states.getValue(node.child))
            is BinaryNode -> automaton.binaryState(node.operator, states.getValue(node.left), states.getValue(node.right))
        }
        return DagConstraintEvaluation(states, states.getValue(dag.root))
    }
}
