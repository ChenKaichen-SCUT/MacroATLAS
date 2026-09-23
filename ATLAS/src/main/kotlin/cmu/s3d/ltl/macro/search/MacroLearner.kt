package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.learning.AlloyMaxBase
import cmu.s3d.ltl.macro.dag.FormulaDag
import cmu.s3d.ltl.macro.dag.FormulaDagRenderer
import edu.mit.csail.sdg.alloy4.A4Reporter
import edu.mit.csail.sdg.parser.CompUtil
import edu.mit.csail.sdg.translator.*
import java.io.File

data class MacroSolveResult(val dag: FormulaDag?, val assignment: MacroAssignment?, val metadata: Map<String, Any>) {
    val formula: String get() = dag?.let { FormulaDagRenderer.render(it) } ?: "UNSAT"
}

enum class MacroCostStrategy { BOUNDED_SAT, WEIGHTED_MAXSAT }

/** Uses the existing AlloyMax backend; no invocation of LTLLearner or post-hoc compression. */
class MacroLearner<Q : Any>(val context: MacroCompilationContext<Q>, private val options: A4Options = AlloyMaxBase.defaultAlloyOptions(),
                          private val reporter: A4Reporter = A4Reporter.NOP,
                          private val costStrategy: MacroCostStrategy = MacroCostStrategy.WEIGHTED_MAXSAT) {
    constructor(plan: MacroConstraintPlan<Q>, positives: List<LassoTrace>, negatives: List<LassoTrace>, options: A4Options = AlloyMaxBase.defaultAlloyOptions(),
                costStrategy: MacroCostStrategy = MacroCostStrategy.WEIGHTED_MAXSAT) :
        this(MacroCompilationContext(plan, positives, negatives), options, A4Reporter.NOP, costStrategy)

    fun solve(debugDirectory: File? = null, printModel: Boolean = false): MacroSolveResult {
        require(options.solver in listOf(A4Options.SatSolver.SAT4JMax, A4Options.SatSolver.OpenWBO, A4Options.SatSolver.OpenWBOWeighted,
            A4Options.SatSolver.POpenWBO, A4Options.SatSolver.POpenWBOAuto)) { "Macro optimization requires an AlloyMax backend" }
        var builder = MacroAlloyModelBuilder(context)
        debugDirectory?.mkdirs()
        fun dump(name: String, text: String) { debugDirectory?.resolve(name)?.writeText(text + "\n") }
        dump("verification.json", metadataJson(mapOf("status" to "IN_PROGRESS")))
        dump("constraint_states.txt", context.registry.states.mapIndexed { i, q -> "$i\t$q" }.joinToString("\n"))
        dump("fiber_catalog.txt", context.catalog.entries.joinToString("\n"))
        var encodingNanos = 0L
        var backendNanos = 0L
        var parseNanos = 0L
        var modelBytes = 0L
        val progressStart = System.nanoTime()
        fun checkpoint(stage: String) {
            val runtime = Runtime.getRuntime()
            dump("stage.json", metadataJson(linkedMapOf(
                "stage" to stage, "elapsedSec" to (System.nanoTime()-progressStart)/1e9,
                "encodingSec" to encodingNanos/1e9, "parseSec" to parseNanos/1e9,
                "backendSec" to backendNanos/1e9, "modelBytes" to modelBytes,
                "heapUsedBytes" to runtime.totalMemory()-runtime.freeMemory(), "heapMaxBytes" to runtime.maxMemory(),
                "fiberCount" to context.catalog.entries.size, "unquotientedFiberCount" to context.catalog.unquotientedSize,
                "encodedFiberCount" to builder.fibers.size, "costScope" to builder.costScope,
                "inputTraceCount" to context.originalPositives.size + context.originalNegatives.size,
                "reducedTraceCount" to context.positives.size + context.negatives.size,
                "positionCount" to builder.positionCount,
                "localPositionAtoms" to builder.localPositionCount, "traceShapeCount" to builder.traceShapes.size)))
        }
        fun build(minimumKept: Int = 0, maximumCost: Int? = null,
                  optimizeCost: Boolean = maximumCost == null, optimizeKept: Boolean = false): String {
            checkpoint("ENCODING")
            val start = System.nanoTime()
            val source = builder.build(minimumKept, maximumCost, optimizeCost, optimizeKept)
            encodingNanos += System.nanoTime() - start
            modelBytes = maxOf(modelBytes, source.toByteArray(Charsets.UTF_8).size.toLong())
            return source
        }
        fun execute(source: String, filename: String): MacroAssignment? {
            dump(filename, source)
            if (printModel) println(source)
            checkpoint("PARSING")
            val backendStart = System.nanoTime()
            val world = CompUtil.parseEverything_fromString(reporter, source)
            parseNanos += System.nanoTime() - backendStart
            checkpoint("TRANSLATING_AND_SOLVING")
            val solution = TranslateAlloyToKodkod.execute_command(reporter, world.allReachableSigs, world.allCommands.first(), options)
            backendNanos += System.nanoTime() - backendStart
            checkpoint("EXTRACTING_ASSIGNMENT")
            if (!solution.satisfiable()) return null
            fun eval(expression: String): Any = solution.eval(CompUtil.parseOneExpression_fromString(world, expression))
            fun tuples(expression: String): List<List<String>> = (eval(expression) as A4TupleSet).map { tuple ->
                (0 until tuple.arity()).map { tuple.atom(it).substringAfterLast('/').substringBefore('$') }
            }
            fun single(expression: String) = tuples(expression).singleOrNull()?.single()
            val anchors = (0 until builder.k).mapNotNull { i -> single("A$i.lab")?.let {
                i to AnchorAssignment(it.substring(1).toInt(), single("A$i.state")!!.substring(1).toInt())
            } }.toMap()
            val ports = builder.portNames.mapNotNull { name -> single("$name.target")?.let {
                name to PortAssignment(it.substring(1).toInt(), single("$name.fiber")!!.substring(1).toInt())
            } }.toMap()
            return MacroAssignment(anchors, ports, eval("#(Carrier.cost)").toString().toInt(), eval("#kept").toString().toInt(),
                context.positions.indices.flatMap { i -> tuples("av$i").map {
                    it[0].substring(1).toInt() to builder.offsets[i] + it[1].substring(1).toInt()
                } }.toSet(),
                context.positions.indices.flatMap { i -> tuples("ev$i").map {
                    it[0] to builder.offsets[i] + it[1].substring(1).toInt()
                } }.toSet())
        }
        val start = System.nanoTime()
        val objective = context.plan.objective as? MacroObjective.Repair
        val repair = objective != null
        val smallStart = System.nanoTime()
        val smallOptimum = if (costStrategy == MacroCostStrategy.WEIGHTED_MAXSAT)
            SmallFormulaBound.optimum(context) else null
        val smallNanos = System.nanoTime() - smallStart
        var finalSource: String
        var assignment: MacroAssignment?
        var passes = 0
        if (smallOptimum != null) {
            // An independently checked witness and exhaustive smaller-domain
            // enumeration prove this hard bound is the global minimum.  A SAT
            // solve retains the usual assignment, decoder and final verifier.
            builder = MacroAlloyModelBuilder(context, smallOptimum)
            finalSource = build(maximumCost = smallOptimum, optimizeCost = false)
            assignment = execute(finalSource, "macro_small_$smallOptimum.als"); passes++
            checkNotNull(assignment) { "Small-formula witness was not representable by the macro encoding" }
            check(assignment.expandedSize == smallOptimum)
        } else if (costStrategy == MacroCostStrategy.WEIGHTED_MAXSAT) {
            var scope = minOf(context.plan.nodeBudget, 8)
            finalSource = ""
            assignment = null
            while (true) {
                builder = MacroAlloyModelBuilder(context, scope)
                if (objective == null) {
                    finalSource = build()
                    assignment = execute(finalSource, "macro_scope_$scope.als"); passes++
                } else {
                    // The theoretical upper bound is cheap to encode tightly: if every
                    // old edge is kept, every endpoint is active and the remaining slot
                    // count follows directly from the size scope.  This removes optional
                    // protected/anonymous slot permutations from the common repair case.
                    builder = MacroAlloyModelBuilder(context, scope, objective.oldEdges.size)
                    finalSource = build(minimumKept = objective.oldEdges.size, optimizeCost = true)
                    assignment = execute(finalSource, "repair_scope_${scope}_all_kept.als"); passes++
                    if (assignment != null) {
                        check(assignment.keptEdges == objective.oldEdges.size)
                        break
                    }
                    // Repair is lexicographic: no solution that drops an old edge can
                    // beat a larger solution retaining all of them.  Grow the cost
                    // scope before considering a weaker primary objective.
                    if (scope < context.plan.nodeBudget) {
                        scope = minOf(context.plan.nodeBudget, scope * 2)
                        continue
                    }
                    // AlloyMax 1.0.3 mishandles maxsome when its expression simplifies to
                    // constant false.  Prove that at least one old edge is feasible before
                    // using its native prioritized MaxSAT objective.  When it is feasible,
                    // maxsome[2] kept + minsome cost is the exact repair lexicographic goal
                    // used by the artifact, without a sequence of hard UNSAT upper bounds.
                    builder = MacroAlloyModelBuilder(context, scope, 1)
                    val hasKeptSource = build(minimumKept = 1, maximumCost = scope, optimizeCost = false)
                    val hasKept = execute(hasKeptSource, "repair_scope_${scope}_has_kept.als"); passes++
                    if (hasKept != null) {
                        finalSource = build(maximumCost = scope, optimizeCost = true, optimizeKept = true)
                        assignment = execute(finalSource, "repair_scope_${scope}_optimal.als"); passes++
                        checkNotNull(assignment)
                    } else {
                        builder = MacroAlloyModelBuilder(context, scope)
                        finalSource = build()
                        assignment = execute(finalSource, "repair_scope_${scope}_zero_kept.als"); passes++
                        check(assignment == null || assignment.keptEdges == 0)
                    }
                }
                if (assignment != null && (objective == null || assignment.keptEdges == objective.oldEdges.size || scope == context.plan.nodeBudget)) {
                    break
                }
                if (scope == context.plan.nodeBudget) break
                scope = minOf(context.plan.nodeBudget, scope * 2)
            }
        } else {
            builder = MacroAlloyModelBuilder(context)
            // Monotone hard bounds preserve the exact lexicographic objectives while
            // avoiding one monolithic optimization of the auxiliary cost relation.
            finalSource = build(maximumCost = context.plan.nodeBudget, optimizeCost = false)
            assignment = execute(finalSource, "macro_model.als"); passes++
            if (assignment != null && objective != null) {
                var low = assignment.keptEdges
                var high = objective.oldEdges.size
                while (low < high) {
                    val middle = low + (high-low+1)/2
                    val source = build(minimumKept = middle, maximumCost = context.plan.nodeBudget, optimizeCost = false)
                    val candidate = execute(source,"repair_bound_$middle.als"); passes++
                    if (candidate == null) high = middle-1 else {
                        check(candidate.keptEdges >= middle)
                        low = candidate.keptEdges; assignment = candidate; finalSource = source
                    }
                }
            }
            if (assignment != null) {
                val kept = assignment.keptEdges
                var low = 1
                var high = assignment.expandedSize
                while (low < high) {
                    val middle = low + (high-low)/2
                    val source = build(minimumKept = kept, maximumCost = middle, optimizeCost = false)
                    val candidate = execute(source,"size_bound_$middle.als"); passes++
                    if (candidate == null) low = middle+1 else {
                        check(candidate.expandedSize <= middle && candidate.keptEdges >= kept)
                        high = candidate.expandedSize; assignment = candidate; finalSource = source
                    }
                }
                check(checkNotNull(assignment).expandedSize == low)
            }
        }
        dump("macro_model.als", finalSource)
        val solverNanos = System.nanoTime() - start
        val decodeStart = System.nanoTime()
        checkpoint("DECODING")
        val decoded = assignment?.let { MacroAssignmentDecoder.decode(context,it) }
        val decodeNanos = System.nanoTime() - decodeStart
        val verifyStart = System.nanoTime()
        checkpoint("VERIFYING")
        val dag = assignment?.let {
            try { FinalSolutionVerifier.verify(context, it, checkNotNull(decoded)) }
            catch (e: Exception) { throw MacroVerificationException(e) }
        }
        val verifyNanos = System.nanoTime() - verifyStart
        val metadata = linkedMapOf<String, Any>(
            "solverMode" to "MACRO", "nodeBudget" to context.plan.nodeBudget, "binaryBudget" to context.plan.binaryBudget,
            "costStrategy" to costStrategy.name,
            "protectedCount" to context.plan.protectedIdentities.size, "anchorSlotBudget" to builder.k,
            "inputTraceCount" to context.originalPositives.size + context.originalNegatives.size,
            "reducedTraceCount" to context.positives.size + context.negatives.size,
            "constraintStateCount" to context.registry.states.size, "fiberCount" to context.catalog.entries.size,
            "unquotientedFiberCount" to context.catalog.unquotientedSize,
            "encodedFiberCount" to builder.fibers.size, "costScope" to builder.costScope,
            "portSlotCount" to builder.portNames.size, "semanticValuationCount" to (builder.k + builder.portNames.size) * builder.positionCount,
            "localPositionAtoms" to builder.localPositionCount, "traceShapeCount" to builder.traceShapes.size,
            "activeAnchorCount" to (assignment?.anchors?.size ?: 0), "activeMacroEdgeCount" to (assignment?.ports?.size ?: 0),
            "expandedNodeCount" to (assignment?.expandedSize ?: 0),
            "binaryNodeCount" to (assignment?.anchors?.values?.count { context.plan.labels[it.label] is MacroLabel.Binary } ?: 0),
            "objectiveValue" to (assignment?.let { if (repair) "kept=${it.keptEdges},size=${it.expandedSize}" else "size=${it.expandedSize}" } ?: "none"),
            "solverStatus" to if (assignment == null) "UNSAT" else "OPTIMAL", "optimizationPasses" to passes,
            "modelBytes" to modelBytes, "semanticTypeCount" to context.catalog.entries.map { it.key.semanticType }.distinct().size,
            "selectedFiberCount" to (assignment?.ports?.values?.map { it.fiber }?.distinct()?.size ?: 0),
            "meanRepresentativeLength" to (assignment?.ports?.values?.map { context.catalog.entries[it.fiber].length }?.average()?.takeUnless { it.isNaN() } ?: 0.0),
            "maxRepresentativeLength" to (assignment?.ports?.values?.maxOfOrNull { context.catalog.entries[it.fiber].length } ?: 0),
            "registrySec" to context.registryNanoseconds/1e9, "fiberSec" to context.fiberNanoseconds/1e9,
            "smallFormulaSec" to smallNanos/1e9, "smallFormulaBound" to (smallOptimum ?: 0),
            "encodingSec" to encodingNanos/1e9, "solverSec" to backendNanos/1e9,
            "parseSec" to parseNanos/1e9, "translationAndSolveSec" to (backendNanos-parseNanos)/1e9,
            "decodeSec" to decodeNanos/1e9, "verifySec" to verifyNanos/1e9
        )
        dump("analysis.json", metadataJson(metadata))
        dump("timing.json", metadataJson(mapOf("solverNanoseconds" to solverNanos)))
        dump("macro_assignment.txt", assignment?.toString() ?: "UNSAT")
        dump("reconstructed_formula.txt", dag?.let { FormulaDagRenderer.render(it) } ?: "UNSAT")
        dump("verification.json", metadataJson(mapOf("status" to if (dag == null) "NOT_APPLICABLE_UNSAT" else "PASSED")))
        checkpoint("COMPLETE")
        return MacroSolveResult(dag, assignment, metadata)
    }
}

class MacroVerificationException(cause: Exception) : IllegalStateException("Macro solution verification failed", cause)

fun metadataJson(values: Map<String, Any>): String {
    fun quote(s: String) = "\"" + s.flatMap { c -> when(c) {
        '\\' -> "\\\\".toList(); '"' -> "\\\"".toList(); '\n' -> "\\n".toList(); '\r' -> "\\r".toList(); '\t' -> "\\t".toList()
        else -> if (c < ' ') "\\u%04x".format(c.code).toList() else listOf(c)
    } }.joinToString("") + "\""
    return values.entries.joinToString(",", "{", "}") { (k,v) -> quote(k) + ":" + if (v is Number || v is Boolean) v.toString() else quote(v.toString()) }
}
