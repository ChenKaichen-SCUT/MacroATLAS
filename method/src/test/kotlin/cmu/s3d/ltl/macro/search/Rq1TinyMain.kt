package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.experiment.BackendMetrics
import cmu.s3d.ltl.experiment.MatchedAtlasLearner
import cmu.s3d.ltl.learning.AlloyMaxBase
import cmu.s3d.ltl.macro.analysis.DagConstraintEvaluator
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.PortKind
import cmu.s3d.ltl.samples2ltl.Task
import cmu.s3d.ltl.samples2ltl.TaskParser
import edu.mit.csail.sdg.translator.A4Options
import java.io.File
import kotlin.system.exitProcess

/** One RQ1 tiny case and one method per JVM; writes a machine-readable result. */
object Rq1TinyMain {
    @JvmStatic fun main(args: Array<String>) {
        require(args.size % 2 == 0)
        val a = args.toList().chunked(2).associate { it[0].removePrefix("--") to it[1] }
        val output = File(a.getValue("output")).apply { mkdirs() }
        val mode = a.getValue("mode")
        require(mode in setOf("oracle", "atlas-b", "macro"))
        val data = linkedMapOf<String, Any>("mode" to mode, "status" to "ERROR")
        val start = System.nanoTime()
        try {
            val task = TaskParser.parseTask(File(a.getValue("file")).readText())
            val B = a.getValue("B").toInt()
            val b = a.getValue("b").toInt()
            val analysis = RecognizedConstraintAnalyzer.analyze(task, b, B) as? MacroTaskAnalysis.Supported
                ?: error("Generated case is not in the matched domain")
            data["B"] = B; data["b"] = b
            data["numAP"] = task.literals.size
            data["positiveTraceCount"] = task.positiveExamples.size
            data["negativeTraceCount"] = task.negativeExamples.size
            data["maxTraceLength"] = (task.positiveExamples + task.negativeExamples).maxOf { it.length() }
            data["recognizedFeatures"] = analysis.recognizedFeatures.joinToString(";")
            fun <Q : Any> execute(plan: MacroConstraintPlan<Q>) {
                data["p"] = plan.protectedIdentities.size
                data["K"] = plan.anchorSlotBudget
                data["objectiveKind"] = if (plan.objective is MacroObjective.Repair) "REPAIR" else "MIN_EXPANDED_SIZE"
                if (mode == "oracle") {
                    val optimum = TinyReferenceEnumerator.optimum(plan, task.positiveExamples, task.negativeExamples)
                    data["status"] = if (optimum == null) "UNSAT" else "SAT"
                    data["objectivePrimary"] = optimum?.kept ?: 0
                    data["objectiveSecondary"] = optimum?.size ?: 0
                    data["candidateDags"] = TinyReferenceEnumerator.candidates(plan).size
                    data["verification"] = "REFERENCE_EXHAUSTIVE"
                    return
                }
                val options = AlloyMaxBase.defaultAlloyOptions().apply { solver = A4Options.SatSolver.OpenWBOWeighted }
                val reporter = BackendMetrics()
                val result = if (mode == "atlas-b") MatchedAtlasLearner(task, plan, options, reporter).solve(output)
                             else MacroLearner(MacroCompilationContext(plan, task.positiveExamples, task.negativeExamples), options, reporter).solve(output)
                output.resolve("solver-metadata.json").writeText(metadataJson(result.metadata) + "\n")
                data.putAll(result.metadata)
                data.putAll(reporter.metadata())
                val dag = result.dag
                data["status"] = if (dag == null) "UNSAT" else "SAT"
                data["objectivePrimary"] = if (mode == "atlas-b") result.metadata.getValue("objectivePrimary")
                                           else result.assignment?.keptEdges ?: 0
                data["objectiveSecondary"] = if (mode == "atlas-b") result.metadata.getValue("objectiveSecondary")
                                             else result.assignment?.expandedSize ?: 0
                if (dag == null) {
                    data["verification"] = "NOT_APPLICABLE_UNSAT"
                    return
                }
                val metrics = structure(dag)
                data.putAll(metrics)
                val positive = task.positiveExamples.all { ConcreteLassoEvaluator.values(dag, it).getValue(dag.root)[0] }
                val negative = task.negativeExamples.none { ConcreteLassoEvaluator.values(dag, it).getValue(dag.root)[0] }
                val automaton = plan.automaton.isAccepting(DagConstraintEvaluator(plan.automaton).evaluate(dag).rootState)
                val identities = identitiesPass(plan, dag)
                data["positiveTracePassed"] = positive
                data["negativeTracePassed"] = negative
                data["constraintAutomatonPassed"] = automaton
                data["identityConstraintsPassed"] = identities
                data["verification"] = if (positive && negative && automaton && identities) "PASSED" else "FAILED"
                output.resolve("reconstructed_formula.txt").writeText(FormulaDagRenderer.render(dag) + "\n")
                if (data["verification"] != "PASSED") data["status"] = "VERIFICATION_FAILED"
            }
            execute(analysis.plan)
        } catch (e: Exception) {
            data["status"] = if (data["status"] == "VERIFICATION_FAILED") "VERIFICATION_FAILED" else "ERROR"
            data["error"] = "${e.javaClass.simpleName}: ${e.message}"
            e.printStackTrace(System.err)
        } finally {
            data["totalSec"] = (System.nanoTime() - start) / 1e9
            output.resolve("result.json").writeText(metadataJson(data) + "\n")
        }
        if (data["status"] in setOf("ERROR", "VERIFICATION_FAILED")) exitProcess(1)
    }

    private fun structure(dag: FormulaDag): Map<String, Any> {
        val depths = hashMapOf<NodeId, Int>()
        for (id in dag.postOrder()) depths[id] = when (val node = dag.node(id)) {
            is LiteralNode -> 0
            is UnaryNode -> 1 + depths.getValue(node.child)
            is BinaryNode -> maxOf(depths.getValue(node.left), depths.getValue(node.right))
        }
        val values = dag.nodes.values
        return linkedMapOf("finalFormulaSize" to dag.size(), "dagNodeCount" to dag.size(),
            "binaryNodeCount" to values.count { it is BinaryNode },
            "unaryNodeCount" to values.count { it is UnaryNode },
            "unaryDepth" to depths.getValue(dag.root),
            "hasSharing" to values.any { dag.parents(it.id).size > 1 })
    }

    private fun <Q : Any> identitiesPass(plan: MacroConstraintPlan<Q>, dag: FormulaDag): Boolean {
        val values = dag.nodes
        for (id in plan.requiredProtectedIdentities) if (id !in values) return false
        for (spec in plan.protectedIdentities) {
            val node = values[spec.id] ?: continue
            val labelOkay = when (val label = spec.label) {
                is MacroLabel.Literal -> node is LiteralNode && node.proposition == label.proposition
                is MacroLabel.Unary -> node is UnaryNode && node.operator == label.operator
                is MacroLabel.Binary -> node is BinaryNode && node.operator == label.operator
            }
            if (!labelOkay) return false
        }
        if (plan.uniqueLiteralIdentities && values.values.filterIsInstance<LiteralNode>().map { it.proposition }.distinct().size !=
            values.values.count { it is LiteralNode }) return false
        fun descendants(id: NodeId): Set<NodeId> {
            val seen = hashSetOf<NodeId>()
            fun visit(next: NodeId) { if (seen.add(next)) dag.children(next).forEach(::visit) }
            if (id in values) dag.children(id).forEach(::visit)
            return seen
        }
        for (constraint in plan.identityConstraints) {
            val okay = when (constraint) {
                is MacroIdentityConstraint.NoDAGReuse -> values.values.all {
                    (constraint.excludeLiterals && it is LiteralNode) || dag.parents(it.id).size <= 1
                }
                MacroIdentityConstraint.NoSharedLiteralBranches -> values.values.filterIsInstance<BinaryNode>().all { node ->
                    (descendants(node.left) + node.left).filter { values[it] is LiteralNode }.toSet()
                        .intersect((descendants(node.right) + node.right).filter { values[it] is LiteralNode }.toSet()).isEmpty()
                }
                is MacroIdentityConstraint.LeftNotEqualRight -> values.values.filterIsInstance<BinaryNode>().all { it.left != it.right }
                is MacroIdentityConstraint.NamedRoot -> dag.root == constraint.target
                is MacroIdentityConstraint.NamedDirectChild -> when (val node = values[constraint.source]) {
                    is UnaryNode -> constraint.port == PortKind.CHILD && node.child == constraint.target
                    is BinaryNode -> (if (constraint.port == PortKind.LEFT) node.left else node.right) == constraint.target
                    else -> false
                }
                is MacroIdentityConstraint.NamedReachability -> constraint.target in descendants(constraint.source)
            }
            if (!okay) return false
        }
        return true
    }
}
