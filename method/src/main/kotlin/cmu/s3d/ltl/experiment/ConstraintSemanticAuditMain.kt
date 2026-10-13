package cmu.s3d.ltl.experiment

import cmu.s3d.ltl.samples2ltl.TaskParser
import cmu.s3d.ltl.macro.search.*
import java.io.File

/** Read-only batch inspection of the real parser and analyzer; no solver is launched. */
object ConstraintSemanticAuditMain {
    @JvmStatic fun main(args: Array<String>) {
        require(args.size == 2) { "Usage: ConstraintSemanticAuditMain <input-root> <task-B-b.tsv>" }
        val root = File(args[0]).canonicalFile
        for (line in File(args[1]).readLines().filter { it.isNotBlank() }) {
            val parts = line.split('\t')
            require(parts.size == 3)
            val (name, budget, binaryBudget) = parts
            val input = File(root, name).canonicalFile
            require(input.path.startsWith(root.path + File.separator))
            val task = TaskParser.parseTask(input.readText())
            val analysis = RecognizedConstraintAnalyzer.analyze(task, binaryBudget.toInt(), budget.toInt())
            val common = linkedMapOf<String, Any>(
                "task" to name, "parsedB" to task.maxNumOfOP + task.literals.size,
                "B" to budget.toInt(), "b" to binaryBudget.toInt(),
                "literals" to task.literals.joinToString(";"),
                "excludedOperators" to task.excludedOperators.joinToString(";"),
                "customText" to (task.customConstraints ?: ""))
            when (analysis) {
                is MacroTaskAnalysis.Unsupported -> {
                    common["supported"] = false
                    common["reason"] = analysis.reasons.joinToString(";")
                    common["detail"] = analysis.detail
                }
                is MacroTaskAnalysis.Supported -> {
                    val plan = analysis.plan
                    common["supported"] = true
                    common["features"] = analysis.recognizedFeatures.joinToString(";")
                    common["automaton"] = plan.automaton.javaClass.simpleName
                    common["allowedUnary"] = plan.allowedUnaryOperators.joinToString(";")
                    common["allowedBinary"] = plan.allowedBinaryOperators.joinToString(";")
                    common["protectedIdentities"] = plan.protectedIdentities.joinToString(";") { "${it.id.value}:${it.label}" }
                    common["requiredProtectedIdentities"] = plan.requiredProtectedIdentities.joinToString(";") { it.value }
                    common["identityConstraints"] = plan.identityConstraints.joinToString(";") { when (it) {
                        is MacroIdentityConstraint.NoDAGReuse -> "NoDAGReuse(excludeLiterals=${it.excludeLiterals})"
                        MacroIdentityConstraint.NoSharedLiteralBranches -> "NoSharedLiteralBranches"
                        MacroIdentityConstraint.LeftNotEqualRight -> "LeftNotEqualRight"
                        is MacroIdentityConstraint.NamedRoot -> "NamedRoot(${it.target.value})"
                        is MacroIdentityConstraint.NamedDirectChild -> "NamedDirectChild(${it.source.value},${it.port},${it.target.value})"
                        is MacroIdentityConstraint.NamedReachability -> "NamedReachability(${it.source.value},${it.target.value})"
                    } }
                    common["requiredRootUnary"] = plan.requiredRootUnary?.toString() ?: ""
                    common["uniqueLiteralIdentities"] = plan.uniqueLiteralIdentities
                    common["objective"] = if (plan.objective is MacroObjective.Repair) "Repair" else "MinExpandedSize"
                    common["oldEdges"] = (plan.objective as? MacroObjective.Repair)?.oldEdges?.joinToString(";") {
                        "${it.source.value}->${it.target.value}" } ?: ""
                    common["anchorSlotBudget"] = plan.anchorSlotBudget
                }
            }
            println(metadataJson(common))
        }
    }
}
