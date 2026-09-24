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
        if(a["mode"]=="inspect") {
            val task=TaskParser.parseTask(File(a.getValue("file")).readText())
            val nodeBudget=a["B"]?.toInt() ?: task.maxNumOfOP+task.literals.size
            val analysis=RecognizedConstraintAnalyzer.analyze(task,b,nodeBudget)
            val result=when(analysis) {
                is MacroTaskAnalysis.Supported -> {
                    val plan=analysis.plan
                    mapOf<String,Any>("supported" to true,"nodeBudget" to plan.nodeBudget,
                        "binaryBudget" to plan.binaryBudget,"protectedCount" to plan.protectedIdentities.size,
                        "anchorSlotBudget" to plan.anchorSlotBudget,
                        "constraintStateCount" to ConstraintStateRegistry(plan).states.size,
                        "recognizedFeatures" to analysis.recognizedFeatures.joinToString(";"))
                }
                is MacroTaskAnalysis.Unsupported -> mapOf<String,Any>("supported" to false,
                    "reason" to analysis.reasons.joinToString(";"),"detail" to analysis.detail)
            }
            directory.resolve("inspect.json").writeText(metadataJson(result)+"\n")
            return
        }
        if(a["mode"]=="emit-scope") {
            val task=TaskParser.parseTask(File(a.getValue("file")).readText())
            val budget=a["B"]?.toInt() ?: task.maxNumOfOP+task.literals.size
            val scope=a.getValue("scope").toInt()
            require(scope in 1..budget)
            val analysis=RecognizedConstraintAnalyzer.analyze(task,b,budget)
            val plan=(analysis as? MacroTaskAnalysis.Supported)?.plan
                ?: error("Same-scope input is unsupported: $analysis")
            val variant=a.getValue("variant")
            val model=when(variant) {
                "atlas-b" -> MatchedAtlasLearner(task,plan,AlloyMaxBase.defaultAlloyOptions()).modelAtScope(scope)
                "macro" -> MacroAlloyModelBuilder(MacroCompilationContext(plan,task.positiveExamples,task.negativeExamples),scope).build()
                else -> error("Expected --variant atlas-b|macro")
            }
            directory.resolve("model.als").writeText(model)
            directory.resolve("model-info.json").writeText(metadataJson(mapOf(
                "variant" to variant,"nodeBudget" to budget,"binaryBudget" to b,
                "costScope" to scope,"scopeMeaning" to "expanded_formula_size_upper_bound",
                "objective" to "minimum_expanded_size","solverInvoked" to false,
                "modelBytes" to model.toByteArray().size)) + "\n")
            return
        }
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
            fun runOriginal(reason:String?, detail:String?=null, boundedAttempt:Map<String,Any>?=null) {
                val analysisSec=data["analysisSec"] ?: 0.0
                if(boundedAttempt!=null) write("bounded-attempt.json",boundedAttempt)
                data.clear()
                data.putAll(linkedMapOf("variant" to mode,"status" to "ERROR","solverMode" to "ORIGINAL",
                    "analysisSec" to analysisSec))
                if(reason!=null) data["fallbackReason"]=reason
                if(detail!=null) data["detail"]=detail
                if(boundedAttempt!=null) data["boundedAttemptSec"]=boundedAttempt["solverSec"] ?: 0.0
                data["nodeBudget"]=task.maxNumOfOP+task.literals.size
                data["binaryBudget"]="UNRESTRICTED"
                data["fallbackUsed"]=reason!=null
                write("metadata.json",data);write("analysis.json",data)
                write("input-diagnostics.json",ArtifactVerifier.inputDiagnostics(task))
                val learner=task.buildLearner(options)
                directory.resolve("original_model_template.als").writeText(learner.generateAlloyModel())
                val solveStart=System.nanoTime();val solution=learner.learn();data["solverSec"]=(System.nanoTime()-solveStart)/1e9
                val formula=solution?.getLTL2() ?: "UNSAT"
                data["outcome"]=if(solution==null) "UNSAT" else "SAT"
                data["status"]=if(reason!=null) "FALLBACK" else data.getValue("outcome")
                directory.resolve("reconstructed_formula.txt").writeText(formula+"\n")
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
                    "scope" to "Trace classification under Original input semantics (missing values false); original raw constraints/objective remain enforced by original Alloy backend"))
                directory.resolve("reconstructed_formula.txt").writeText(formula+"\n")
                println("${a.getValue("file")},${task.toCSVString()},${data["solverSec"]},\"$formula\"")
            }
            val unsupported=analysis as? MacroTaskAnalysis.Unsupported
            if(unsupported!=null && mode!="auto") {
                data["fallbackReason"]=unsupported.reasons.joinToString(",")
                data["detail"]=unsupported.detail
                data["status"]="UNSUPPORTED";write("analysis.json",data);return
            }
            val supported=analysis as? MacroTaskAnalysis.Supported
            val structuralFallback=if(mode=="auto" && supported!=null) AutoDomainSafety.precheck(supported) else null
            if(mode=="original" || unsupported!=null || structuralFallback!=null) {
                runOriginal(unsupported?.reasons?.joinToString(",") ?: structuralFallback, unsupported?.detail)
            } else {
                val plan=checkNotNull(supported).plan
                val reporter=BackendMetrics()
                data["solverMode"]=if(mode=="atlas-b") "ATLAS_B" else "MACRO"
                data["nodeBudget"]=plan.nodeBudget;data["binaryBudget"]=plan.binaryBudget
                data["protectedCount"]=plan.protectedIdentities.size;data["anchorSlotBudget"]=plan.anchorSlotBudget
                data["objectiveKind"]=if(plan.objective is MacroObjective.Repair) "REPAIR" else "MIN_EXPANDED_SIZE"
                write("metadata.json",data);write("analysis.json",data)
                fun <Q:Any> solve(p:MacroConstraintPlan<Q>):MacroSolveResult = if(mode=="atlas-b")
                    MatchedAtlasLearner(task,p,options,reporter).solve(directory)
                else {
                    val strategy = when(a["cost-strategy"] ?: "weighted") {
                        "bounded" -> MacroCostStrategy.BOUNDED_SAT
                        "weighted" -> MacroCostStrategy.WEIGHTED_MAXSAT
                        else -> error("Expected --cost-strategy bounded|weighted")
                    }
                    MacroLearner(MacroCompilationContext(p,task.positiveExamples,task.negativeExamples),options,reporter,strategy).solve(directory)
                }
                val result=solve(plan)
                data.putAll(result.metadata);data.putAll(reporter.metadata())
                result.dag?.let { data.putAll(formulaStructure(it)) }
                data["status"]=if(result.dag==null) "UNSAT" else "SAT"
                if(mode=="auto" && result.dag==null) {
                    runOriginal(AutoDomainSafety.BOUNDED_UNSAT,
                        "The b-bounded macro domain is UNSAT; Original determines the unrestricted result",data.toMap())
                } else {
                    if(mode!="atlas-b") {
                        data["objectivePrimary"]=result.assignment?.keptEdges ?: 0
                        data["objectiveSecondary"]=result.assignment?.expandedSize ?: 0
                    }
                    data["objectiveKind"]=if(plan.objective is MacroObjective.Repair) "REPAIR" else "MIN_EXPANDED_SIZE"
                    data["searchNodeUniverse"]=result.metadata["searchNodeUniverse"] ?:
                        if(mode=="atlas-b") plan.nodeBudget+task.literals.size else plan.anchorSlotBudget
                    data["anchorSlotBudget"]=plan.anchorSlotBudget
                    data["nodeBudget"]=plan.nodeBudget;data["binaryBudget"]=plan.binaryBudget
                    data["protectedCount"]=plan.protectedIdentities.size
                    directory.resolve("reconstructed_formula.txt").writeText(result.formula+"\n")
                    println("${a.getValue("file")},${task.toCSVString()},${data["solverSec"]},\"${result.formula}\"")
                }
            }
        } catch(e:Exception) {
            data["status"]=if(e is MacroVerificationException) "VERIFICATION_FAILED" else "ERROR"
            data["error"]="${e.javaClass.simpleName}: ${e.message}"
            write("verification.json",mapOf("status" to "FAILED","detail" to data.getValue("error")))
            e.printStackTrace(System.err)
        } finally {
            data["totalInternalSec"]=(System.nanoTime()-start)/1e9
            write("metadata.json",data);write("analysis.json",data)
            write("timing.json",data.filterKeys { it.endsWith("Sec") })
        }
        if(data["status"] in listOf("ERROR","VERIFICATION_FAILED")) exitProcess(1)
    }

    private fun formulaStructure(dag: FormulaDag): Map<String,Any> {
        val chain=hashMapOf<NodeId,Int>()
        for(id in dag.postOrder()) {
            val node=dag.node(id)
            chain[id]=if(node is UnaryNode) 1+(if(dag.node(node.child) is UnaryNode) chain.getValue(node.child) else 0) else 0
        }
        return mapOf("learnedDagNodes" to dag.size(),
            "learnedUnaryNodes" to dag.nodes.values.count { it is UnaryNode },
            "learnedBinaryNodes" to dag.nodes.values.count { it is BinaryNode },
            "learnedUnaryDepth" to (chain.values.maxOrNull() ?: 0),
            "learnedHasSharing" to dag.nodes.keys.any { dag.indegree(it)>1 })
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
