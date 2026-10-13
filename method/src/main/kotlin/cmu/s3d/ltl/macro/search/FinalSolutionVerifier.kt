package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.macro.analysis.DagConstraintEvaluator
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.*
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Concrete syntax semantics with fixed points, independent of SemanticType and the search equations. */
object ConcreteLassoEvaluator {
    fun values(dag: FormulaDag, trace: LassoTrace): Map<NodeId, BooleanArray> {
        val n = trace.length()
        require(n > 0)
        val loopStart = if (trace.loop.isEmpty()) n - 1 else trace.prefix.size
        fun next(i: Int) = if (i + 1 == n) loopStart else i + 1
        val values = linkedMapOf<NodeId, BooleanArray>()
        for (id in dag.postOrder()) values[id] = when (val node = dag.node(id)) {
            is LiteralNode -> BooleanArray(n) { trace.getStateAt(it).values[node.proposition] == true }
            is UnaryNode -> {
                val c = values.getValue(node.child)
                when (node.operator) {
                    UnaryOperator.NOT -> BooleanArray(n) { !c[it] }
                    UnaryOperator.X -> BooleanArray(n) { c[next(it)] }
                    UnaryOperator.F, UnaryOperator.G -> {
                        val g = node.operator == UnaryOperator.G
                        var v = BooleanArray(n) { g }
                        do {
                            val before = v
                            v = BooleanArray(n) { if (g) c[it] && before[next(it)] else c[it] || before[next(it)] }
                        } while (!v.contentEquals(before))
                        v
                    }
                }
            }
            is BinaryNode -> {
                val l = values.getValue(node.left); val r = values.getValue(node.right)
                BooleanArray(n) { when (node.operator) {
                    BinaryOperator.AND -> l[it] && r[it]
                    BinaryOperator.OR -> l[it] || r[it]
                    BinaryOperator.IMPLIES -> !l[it] || r[it]
                    BinaryOperator.UNTIL -> error("U is outside the macro fragment")
                } }
            }
        }
        return values
    }
}

object FinalSolutionVerifier {
    fun <Q : Any> verify(context: MacroCompilationContext<Q>, assignment: MacroAssignment, decoded: DecodedMacro<Q>): FormulaDag {
        val plan = context.plan
        val macro = decoded.macro
        val roundTrip = MacroRoundTripVerifier.verify(decoded.witness, macro)
        check(roundTrip.isValid) { "Macro round trip failed: ${roundTrip.violations}" }
        val dag = checkNotNull(roundTrip.canonicalDag)
        check(dag.size() == assignment.expandedSize && dag.size() <= plan.nodeBudget)
        check(dag.nodes.values.count { it is BinaryNode } <= plan.binaryBudget)
        check(macro.actualAnchors.size <= plan.anchorSlotBudget)
        if (plan.uniqueLiteralIdentities) check(dag.nodes.values.filterIsInstance<LiteralNode>().map { it.proposition }.distinct().size ==
            dag.nodes.values.count { it is LiteralNode })
        val evaluation = DagConstraintEvaluator(plan.automaton).evaluate(dag)
        check(plan.automaton.isAccepting(evaluation.rootState))
        check(context.originalPositives.all { ConcreteLassoEvaluator.values(dag,it).getValue(dag.root)[0] })
        check(context.originalNegatives.none { ConcreteLassoEvaluator.values(dag,it).getValue(dag.root)[0] })
        for ((i, id) in decoded.slotIds) {
            check(evaluation.stateByNode.getValue(id) == context.registry.states[assignment.anchors.getValue(i).state])
        }
        for ((i, protected) in plan.protectedIdentities.withIndex()) {
            if (i !in decoded.slotIds) {
                check(protected.id !in plan.requiredProtectedIdentities)
                continue
            }
            val n = dag.node(protected.id)
            check(when (val label = protected.label) {
                is MacroLabel.Literal -> n is LiteralNode && n.proposition == label.proposition
                is MacroLabel.Unary -> n is UnaryNode && n.operator == label.operator
                is MacroLabel.Binary -> n is BinaryNode && n.operator == label.operator
            })
        }
        for (c in plan.identityConstraints) check(when (c) {
            is MacroIdentityConstraint.NoDAGReuse -> dag.nodes.values.all { (c.excludeLiterals && it is LiteralNode) || dag.parents(it.id).size <= 1 }
            MacroIdentityConstraint.NoSharedLiteralBranches -> {
                fun literalsBelow(start:NodeId):Set<NodeId> {
                    val seen=hashSetOf<NodeId>();val queue=java.util.ArrayDeque<NodeId>();queue.add(start)
                    while(queue.isNotEmpty()) { val id=queue.remove();if(seen.add(id))dag.children(id).forEach(queue::add) }
                    return seen.filter { dag.node(it) is LiteralNode }.toSet()
                }
                dag.nodes.values.filterIsInstance<BinaryNode>().all { literalsBelow(it.left).intersect(literalsBelow(it.right)).isEmpty() }
            }
            is MacroIdentityConstraint.LeftNotEqualRight -> dag.nodes.values.filterIsInstance<BinaryNode>().all { it.left != it.right }
            is MacroIdentityConstraint.NamedRoot -> dag.root == c.target
            is MacroIdentityConstraint.NamedDirectChild -> when (val n = dag.node(c.source)) {
                is UnaryNode -> c.port == PortKind.CHILD && n.child == c.target
                is BinaryNode -> (if (c.port == PortKind.LEFT) n.left else n.right) == c.target
                else -> false
            }
            is MacroIdentityConstraint.NamedReachability -> {
                val seen = hashSetOf<NodeId>(); val queue = java.util.ArrayDeque<NodeId>()
                dag.children(c.source).forEach { queue.add(it) }
                while (queue.isNotEmpty()) { val id = queue.remove(); if (seen.add(id)) dag.children(id).forEach { queue.add(it) } }
                c.target in seen
            }
        }) { "Identity constraint failed: $c" }
        val old = (plan.objective as? MacroObjective.Repair)?.oldEdges ?: emptySet()
        check(old.count { it.source in dag.nodes && it.target in dag.children(it.source) } == assignment.keptEdges)
        var offset = 0
        for ((traceIndex, pos) in context.positions.withIndex()) {
            val vals = ConcreteLassoEvaluator.values(dag, pos.trace)
            check(vals.getValue(dag.root)[0] == (traceIndex < context.positives.size))
            for ((slot, id) in decoded.slotIds) for (i in pos.successor.indices)
                check(vals.getValue(id)[i] == ((slot to offset+i) in assignment.anchorValues)) { "Anchor valuation mismatch" }
            for ((name, pa) in assignment.ports) {
                val entry = context.catalog.entries[pa.fiber]
                val input = vals.getValue(decoded.slotIds.getValue(pa.target))
                val semantic = pos.evaluate(entry.key.semanticType, input)
                val head = if (name == "R") dag.root else {
                    val node = dag.node(decoded.slotIds.getValue(name.substring(1).toInt()))
                    when (node) {
                        is UnaryNode -> node.child
                        is BinaryNode -> if (name.first() == 'L') node.left else node.right
                        else -> error("Literal with port")
                    }
                }
                check(semantic.contentEquals(vals.getValue(head))) { "Fiber semantic/representative mismatch" }
                for (i in semantic.indices) check(semantic[i] == ((name to offset+i) in assignment.edgeValues)) { "Edge valuation mismatch" }
            }
            offset += pos.successor.size
        }
        return dag
    }
}
