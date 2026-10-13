package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.analysis.MacroEligibility
import cmu.s3d.ltl.macro.analysis.MacroIneligibleException
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.macro.unary.UnaryWord

/** Unique decomposition at literal, binary, protected and shared-unary anchors. */
object AnchorExtractor {
    /** Only eligible graphs may enter decomposition; unsupported inputs fail explicitly. */
    fun <Q : Any> extract(eligibility: MacroEligibility<Q>): RawMacroDag<Q> {
        if (eligibility is MacroEligibility.Unsupported) throw MacroIneligibleException(eligibility.reasons)
        eligibility as MacroEligibility.Eligible<Q>
        val dag = eligibility.dag
        val anchors = dag.nodes.filter { (id, node) ->
            node !is UnaryNode || id in eligibility.protectedNodeIds || dag.indegree(id) > 1
        }
        val edges = LinkedHashMap<MacroPort, RawMacroEdge>()
        val covered = HashSet<NodeId>()
        for (port in portsOf(anchors)) {
            var current = immediateChild(dag, port)
            val operators = ArrayList<UnaryOperator>()
            val ids = ArrayList<NodeId>()
            while (current !in anchors) {
                val node = dag.node(current)
                check(node is UnaryNode) { "Only unary nodes may occur inside a macro edge" }
                check(dag.indegree(current) <= 1 && current !in eligibility.protectedNodeIds)
                check(covered.add(current)) { "Unary identity $current occurs in multiple macro edges" }
                operators.add(node.operator) // Outer to inner, following the original child pointers.
                ids.add(current)
                current = node.child
            }
            edges[port] = RawMacroEdge(port, current, UnaryWord(operators), ids)
        }
        check(covered == dag.nodes.keys - anchors.keys) { "Decomposition failed to cover all non-anchor nodes" }
        val result = RawMacroDag(eligibility, anchors, edges)
        result.statistics.validatePortBudget()
        check(MacroDagExpander.expandOriginal(result) == dag) { "Original decomposition is not lossless" }
        return result
    }
}
