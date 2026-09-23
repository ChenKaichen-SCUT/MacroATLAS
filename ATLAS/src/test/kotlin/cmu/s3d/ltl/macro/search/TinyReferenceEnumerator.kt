package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.macro.analysis.DagConstraintEvaluator
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.PortKind
import cmu.s3d.ltl.macro.kernel.UFreeLassoOracle

/** Test-only exhaustive ordered DAGs, including sharing and repeated children.
 * Every rooted DAG has a topological numbering with its root last. No macro/fiber code is used.
 */
internal object TinyReferenceEnumerator {
    data class Optimum(val kept: Int, val size: Int)
    private val cache = hashMapOf<String, List<FormulaDag>>()
    fun candidates(plan: MacroConstraintPlan<*>): List<FormulaDag> {
        val key = "${plan.labels}/${plan.nodeBudget}/${plan.binaryBudget}"
        return cache.getOrPut(key) {
            val result = arrayListOf<FormulaDag>()
            for (size in 1..plan.nodeBudget) {
                val nodes = arrayListOf<FormulaNode>()
                fun visit(binary: Int) {
                    val i = nodes.size
                    if (i == size) {
                        val reached = hashSetOf<NodeId>()
                        fun walk(id: NodeId) { if (reached.add(id)) nodes[id.value.substring(1).toInt()].children().forEach { walk(it) } }
                        walk(nodes.last().id)
                        if (reached.size == size) result.add(FormulaDag(nodes.last().id, nodes))
                        return
                    }
                    val id = NodeId("n$i")
                    fun add(node: FormulaNode, count: Int = binary) { nodes.add(node); visit(count); nodes.removeAt(nodes.lastIndex) }
                    plan.propositions.forEach { add(LiteralNode(id,it)) }
                    for (op in plan.allowedUnaryOperators) for (j in 0 until i) add(UnaryNode(id,op,NodeId("n$j")))
                    if (binary < plan.binaryBudget) for (op in plan.allowedBinaryOperators) for (l in 0 until i) for (r in 0 until i)
                        add(BinaryNode(id,op,NodeId("n$l"),NodeId("n$r")),binary+1)
                }
                visit(0)
            }
            result
        }
    }

    fun <Q : Any> optimum(plan: MacroConstraintPlan<Q>, positives: List<LassoTrace>, negatives: List<LassoTrace>): Optimum? {
        var best: Optimum? = null
        val repair = plan.objective as? MacroObjective.Repair
        for (dag in candidates(plan)) {
            if (plan.uniqueLiteralIdentities && dag.nodes.values.filterIsInstance<LiteralNode>().map { it.proposition }.distinct().size !=
                dag.nodes.values.count { it is LiteralNode }) continue
            if (repair == null && best != null && dag.size() > best.size) break
            if (!plan.automaton.isAccepting(DagConstraintEvaluator(plan.automaton).evaluate(dag).rootState)) continue
            if (positives.any { !UFreeLassoOracle.evaluate(dag,it)[0] } || negatives.any { UFreeLassoOracle.evaluate(dag,it)[0] }) continue
            val protected = plan.protectedIdentities
            val map = linkedMapOf<NodeId,NodeId>()
            fun assign(i: Int) {
                if (i < protected.size) {
                    val spec = protected[i]
                    for (n in dag.nodes.values) {
                        val matches = when (val l = spec.label) {
                            is MacroLabel.Literal -> n is LiteralNode && n.proposition == l.proposition
                            is MacroLabel.Unary -> n is UnaryNode && n.operator == l.operator
                            is MacroLabel.Binary -> n is BinaryNode && n.operator == l.operator
                        }
                        if (matches && n.id !in map.values) { map[spec.id] = n.id; assign(i+1); map.remove(spec.id) }
                    }
                    return
                }
                for (c in plan.identityConstraints) {
                    val valid = when (c) {
                        is MacroIdentityConstraint.NoDAGReuse -> dag.nodes.values.all { (c.excludeLiterals && it is LiteralNode) || dag.parents(it.id).size <= 1 }
                        MacroIdentityConstraint.NoSharedLiteralBranches -> {
                            fun literalsBelow(start:NodeId):Set<NodeId> {
                                val seen=hashSetOf<NodeId>();fun walk(id:NodeId) { if(seen.add(id))dag.children(id).forEach(::walk) }
                                walk(start);return seen.filter { dag.node(it) is LiteralNode }.toSet()
                            }
                            dag.nodes.values.filterIsInstance<BinaryNode>().all { literalsBelow(it.left).intersect(literalsBelow(it.right)).isEmpty() }
                        }
                        is MacroIdentityConstraint.LeftNotEqualRight -> dag.nodes.values.filterIsInstance<BinaryNode>().all { it.left != it.right }
                        is MacroIdentityConstraint.NamedRoot -> dag.root == map.getValue(c.target)
                        is MacroIdentityConstraint.NamedDirectChild -> {
                            val n = dag.node(map.getValue(c.source)); val t = map.getValue(c.target)
                            when(n) { is UnaryNode -> n.child == t; is BinaryNode -> (if(c.port == PortKind.LEFT) n.left else n.right) == t; else -> false }
                        }
                        is MacroIdentityConstraint.NamedReachability -> {
                            val seen = hashSetOf<NodeId>()
                            fun walk(id: NodeId) { dag.children(id).forEach { if (seen.add(it)) walk(it) } }
                            walk(map.getValue(c.source)); map.getValue(c.target) in seen
                        }
                    }
                    if (!valid) return
                }
                val kept = repair?.oldEdges?.count { map.getValue(it.target) in dag.children(map.getValue(it.source)) } ?: 0
                val candidate = Optimum(kept,dag.size())
                if (best == null || candidate.kept > best!!.kept || (candidate.kept == best!!.kept && candidate.size < best!!.size)) best = candidate
            }
            assign(0)
        }
        return best
    }
}
