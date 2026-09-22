package cmu.s3d.ltl.experiment

import cmu.s3d.ltl.learning.AlloyMaxBase
import cmu.s3d.ltl.samples2ltl.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.search.*
import edu.mit.csail.sdg.translator.A4Options
import java.io.File
import kotlin.system.exitProcess

/** Separate experiment entry point: exactly one task/JVM. CLI OFF remains byte-for-byte compatible. */
object ExperimentMain {
    @JvmStatic fun main(args: Array<String>) {
        require(args.size%2==0) { "Expected --key value pairs" }
        val a=args.toList().chunked(2).associate { it[0].removePrefix("--") to it[1] }
        val b=a["b"]?.toInt() ?: 2
        val directory=File(a.getValue("output")).apply { mkdirs() }
        if(a["mode"]=="coverage") { coverage(File(a.getValue("root")),b,directory);return }
        val data=linkedMapOf<String,Any>("variant" to a.getValue("mode"),"status" to "ERROR","solverMode" to "NONE")
        val start=System.nanoTime()
        fun write(name:String,values:Map<String,Any>)=directory.resolve(name).writeText(metadataJson(values)+"\n")
        write("verification.json",mapOf("status" to "IN_PROGRESS"))
        try {
            val task=TaskParser.parseTask(File(a.getValue("file")).readText())
            data["nodeBudget"]=a["B"]?.toInt() ?: task.maxNumOfOP+task.literals.size
            data["binaryBudget"]=if(a["mode"]=="original") "UNRESTRICTED" else b
            val options=AlloyMaxBase.defaultAlloyOptions().apply { solver=A4Options.SatSolver.OpenWBOWeighted }
            val mode=a.getValue("mode")
            require(mode in listOf("original","atlas-b","macro","auto"))
            val analyzeStart=System.nanoTime()
            val analysis=if(mode=="original") null else RecognizedConstraintAnalyzer.analyze(task,b,a["B"]?.toInt() ?: task.maxNumOfOP+task.literals.size)
            data["analysisSec"]=(System.nanoTime()-analyzeStart)/1e9
            var fallback=false
            when(analysis) {
                is MacroTaskAnalysis.Unsupported -> {
                    data["fallbackReason"]=analysis.reasons.joinToString(",");data["detail"]=analysis.detail
                    if(mode!="auto") {data["status"]="UNSUPPORTED";write("analysis.json",data);return}
                    fallback=true
                }
                else -> Unit
            }
            if(mode=="original"||fallback) {
                data["solverMode"]="ORIGINAL"
                data["nodeBudget"]=task.maxNumOfOP+task.literals.size
                data["binaryBudget"]="UNRESTRICTED"
                data["fallbackUsed"]=fallback
                write("metadata.json",data);write("analysis.json",data)
                val learner=task.buildLearner(options)
                directory.resolve("original_model_template.als").writeText(learner.generateAlloyModel())
                val solveStart=System.nanoTime();val solution=learner.learn();data["solverSec"]=(System.nanoTime()-solveStart)/1e9
                val formula=solution?.getLTL2() ?: "UNSAT"
                data["outcome"]=if(solution==null) "UNSAT" else "SAT"
                data["status"]=if(fallback) "FALLBACK" else data.getValue("outcome")
                directory.resolve("reconstructed_formula.txt").writeText(formula+"\n")
                // Keep the original solver outcome, but never call a partial valuation verified.
                // An invalid artifact input is an ERROR; a wrong result on valid input still stops the campaign.
                ArtifactVerifier.requireConcreteInput(task)
                if(solution!=null) {
                    val verifyStart=System.nanoTime();val dag=AlloySolutionDagExtractor().extract(solution)
                    directory.resolve("reconstructed_formula.txt").writeText(formula+"\n")
                    try {
                        check(task.positiveExamples.all { ArtifactVerifier.evaluate(dag,it) } && task.negativeExamples.none { ArtifactVerifier.evaluate(dag,it) }) {
                            "Original ATLAS output fails concrete trace classification: $formula"
                        }
                    } catch(e:Exception) { throw MacroVerificationException(e) }
                    data["verifySec"]=(System.nanoTime()-verifyStart)/1e9;data["expandedNodeCount"]=dag.size()
                    data["matchesExpected"]=formula in task.expected
                }
                write("verification.json",mapOf("status" to if(solution==null) "NOT_APPLICABLE_UNSAT" else "TRACE_PASSED",
                    "scope" to "Concrete trace classification; original raw constraints/objective remain enforced by original Alloy backend"))
                directory.resolve("reconstructed_formula.txt").writeText(formula+"\n")
                println("${a.getValue("file")},${task.toCSVString()},${data["solverSec"]},\"$formula\"")
            } else {
                val plan=(analysis as MacroTaskAnalysis.Supported).plan
                val reporter=BackendMetrics()
                data["solverMode"]=if(mode=="atlas-b") "ATLAS_B" else "MACRO"
                data["nodeBudget"]=plan.nodeBudget;data["binaryBudget"]=plan.binaryBudget
                data["protectedCount"]=plan.protectedIdentities.size;data["anchorSlotBudget"]=plan.anchorSlotBudget
                data["objectiveKind"]=if(plan.objective is MacroObjective.Repair) "REPAIR" else "MIN_EXPANDED_SIZE"
                write("metadata.json",data);write("analysis.json",data)
                fun <Q:Any> solve(p:MacroConstraintPlan<Q>):MacroSolveResult = if(mode=="atlas-b")
                    MatchedAtlasLearner(task,p,options,reporter).solve(directory)
                else MacroLearner(MacroCompilationContext(p,task.positiveExamples,task.negativeExamples),options,reporter).solve(directory)
                val result=solve(plan)
                data.putAll(result.metadata);data.putAll(reporter.metadata())
                data["status"]=if(result.dag==null) "UNSAT" else "SAT"
                if(mode!="atlas-b") {
                    data["objectivePrimary"]=result.assignment?.keptEdges ?: 0
                    data["objectiveSecondary"]=result.assignment?.expandedSize ?: 0
                }
                data["objectiveKind"]=if(plan.objective is MacroObjective.Repair) "REPAIR" else "MIN_EXPANDED_SIZE"
                data["searchNodeUniverse"]=if(mode=="atlas-b") plan.nodeBudget+task.literals.size else plan.anchorSlotBudget
                data["anchorSlotBudget"]=plan.anchorSlotBudget
                data["nodeBudget"]=plan.nodeBudget;data["binaryBudget"]=plan.binaryBudget
                data["protectedCount"]=plan.protectedIdentities.size
                directory.resolve("reconstructed_formula.txt").writeText(result.formula+"\n")
                println("${a.getValue("file")},${task.toCSVString()},${data["solverSec"]},\"${result.formula}\"")
            }
        } catch(e:Exception) {
            data["status"]=if(e is MacroVerificationException) "VERIFICATION_FAILED" else "ERROR"
            data["error"]="${e.javaClass.simpleName}: ${e.message}"
            write("verification.json",mapOf("status" to if(e is InvalidArtifactTraceException) "INVALID_INPUT" else "FAILED","detail" to data.getValue("error")))
            e.printStackTrace(System.err)
        } finally {
            data["totalInternalSec"]=(System.nanoTime()-start)/1e9
            write("metadata.json",data);write("analysis.json",data)
            write("timing.json",data.filterKeys { it.endsWith("Sec") })
        }
        if(data["status"] in listOf("ERROR","VERIFICATION_FAILED")) exitProcess(1)
    }

    private fun coverage(root:File,b:Int,directory:File) {
        val rows=arrayListOf<String>();val supported=arrayListOf<String>()
        fun csv(xs:List<Any>)=xs.joinToString(","){"\"${it.toString().replace("\"","\"\"")}\""}
        rows.add(csv(listOf("task","family","supported","reason","nodeBudget","operatorSet","binaryBudgetUsed","protectedCount","recognizedFeatures")))
        for(file in root.walkTopDown().filter { it.isFile&&it.extension=="trace" }.sortedBy { it.relativeTo(root).invariantSeparatorsPath }) {
            val path=file.relativeTo(root).invariantSeparatorsPath
            try {
                val task=TaskParser.parseTask(file.readText());val analysis=RecognizedConstraintAnalyzer.analyze(task,b)
                val supportedPlan=(analysis as? MacroTaskAnalysis.Supported)?.plan
                val reason=(analysis as? MacroTaskAnalysis.Unsupported)?.reasons?.joinToString(";") ?: "SUPPORTED_MACRO"
                if(supportedPlan!=null)supported.add(path)
                rows.add(csv(listOf(path,path.substringBefore('/'),supportedPlan!=null,reason,task.maxNumOfOP+task.literals.size,
                    (listOf("Neg","X","F","G","And","Or","Imply","Until")-task.excludedOperators.toSet()).joinToString(";"),b,
                    supportedPlan?.protectedIdentities?.size ?: "",(analysis as? MacroTaskAnalysis.Supported)?.recognizedFeatures?.joinToString(";") ?: "")))
            } catch(e:Exception) { rows.add(csv(listOf(path,path.substringBefore('/'),false,"OTHER_INPUT_FORMAT", "","",b,"","${e.javaClass.simpleName}: ${e.message}"))) }
        }
        directory.resolve("coverage.csv").writeText(rows.joinToString("\n")+"\n")
        directory.resolve("supported_tasks.txt").writeText(supported.joinToString("\n",postfix=if(supported.isEmpty()) "" else "\n"))
    }
}
