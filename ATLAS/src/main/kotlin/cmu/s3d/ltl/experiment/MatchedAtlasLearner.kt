package cmu.s3d.ltl.experiment

import cmu.s3d.ltl.learning.*
import cmu.s3d.ltl.samples2ltl.Task
import cmu.s3d.ltl.macro.analysis.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.kernel.*
import cmu.s3d.ltl.macro.search.*
import edu.mit.csail.sdg.alloy4.A4Reporter
import edu.mit.csail.sdg.parser.CompUtil
import edu.mit.csail.sdg.translator.*
import java.io.File

/** Experimental ATLAS-B: original concrete syntax/trace encoding, matched bounds and objectives.
 * Original ATLAS itself is unchanged and is reproduced separately.
 */
class MatchedAtlasLearner<Q : Any>(private val task: Task, private val plan: MacroConstraintPlan<Q>,
                                 private val options: A4Options, private val reporter: A4Reporter = A4Reporter.NOP) {
    private val repair = plan.objective as? MacroObjective.Repair
    private val source = task.buildLearner(options, minimized = false)
    private fun union(xs: List<String>, empty: String = "none") = xs.joinToString(" + ").ifEmpty { empty }
    private fun template(costScope: Int): String {
        // The analyzer has accepted the entire input. Remove exactly its one supported soft objective.
        val raw = (task.customConstraints ?: "").replace(Regex("/\\*[\\s\\S]*?\\*/|//[^\\n]*|--[^\\n]*"), " ")
        val objective = Regex("maxsome\\s*\\[\\s*2\\s*]\\s*subDAG\\s*\\[\\s*root\\s*]\\s*&\\s*\\([^(){}]*\\)")
        check(objective.findAll(raw).count() == if (repair == null) 0 else 1)
        // Keep a surrounding fact block intact when the objective shares it with hard
        // clauses, as in the official Robot tasks.
        val hard = objective.replace(raw, "none = none")
        val learner = task.copy(customConstraints = hard).buildLearner(options, minimized = false)
        var model = learner.generateAlloyModel()
        // Original generator emits `next =` for a one-position task. This experimental
        // variant supplies the mathematically identical empty binary relation; OFF is untouched.
        model = model.replace(Regex("(?m)^(\\s*)next =\\s*$"), "$1ordering/next = none->none")
        // Shorter traces must not follow global ordering edges outside their own range.
        // Original ATLAS remains untouched; ATLAS-B must match concrete lasso semantics.
        model = model.replace("i.(next+lasso)", "i.((next :> seqRange) + lasso)")
        val binaries = union(plan.allowedBinaryOperators.map { it.atlasName })
        val pairs = union(repair?.oldEdges?.map { "${it.source.value}->${it.target.value}" } ?: emptyList(),"none->none")
        val namedNonLiterals = union(plan.protectedIdentities.filter { it.label !is MacroLabel.Literal }.map { it.id.value })
        val extra = """
            fun experimentReach: set DAGNode { childrenAndSelfOf[root] }
            fun experimentKept: DAGNode -> DAGNode { ($pairs) & subDAG[root] }
            one sig ExperimentCost { used: set DAGNode }
            fact { ExperimentCost.used = experimentReach }
            fact ExperimentBounds {
              DAGNode = experimentReach + Literal + ($namedNonLiterals)
              #experimentReach <= $costScope
              #(experimentReach & ($binaries)) <= ${plan.binaryBudget}
              minsome ExperimentCost.used
            }
        """.trimIndent()
        // Irrelevant APs exist in original ATLAS as one sig literals, but do not consume rooted size B.
        val scope = costScope + task.literals.size + plan.protectedIdentities.count { it.label !is MacroLabel.Literal }
        val maxCardinality = maxOf(scope,repair?.oldEdges?.size ?: 0)
        val bits = 2 + (31 - Integer.numberOfLeadingZeros(maxCardinality))
        return model.replace("run {",extra+"\nrun {").replace("for %d DAGNode","for $scope DAGNode, $bits Int")
    }

    fun solve(directory: File): MacroSolveResult {
        directory.mkdirs()
        var encodingNanos = 0L; var solverNanos = 0L; var decodeNanos = 0L; var verifyNanos = 0L
        var modelBytes = 0
        fun execute(bound: Int, costScope: Int): Pair<FormulaDag,Int>? {
            val begin = System.nanoTime(); val base = template(costScope); encodingNanos += System.nanoTime()-begin
            val model = if (bound == 0) base else base + "\nfact { #experimentKept >= $bound }\n"
            modelBytes=maxOf(modelBytes,model.toByteArray().size)
            directory.resolve("baseline_scope_${costScope}_bound_$bound.als").writeText(model)
            val start = System.nanoTime()
            val world=CompUtil.parseEverything_fromString(reporter,model)
            val solution=TranslateAlloyToKodkod.execute_command(reporter,world.allReachableSigs,world.allCommands.first(),options)
            solverNanos+=System.nanoTime()-start
            if(!solution.satisfiable()) return null
            val decode=System.nanoTime()
            val wrapped=LTLLearningSolution(source,world,solution,plan.nodeBudget,1)
            val raw=AlloySolutionDagExtractor().extract(wrapped)
            val protected=plan.protectedIdentities.map { it.id }.toSet()
            val names=raw.nodes.keys.associateWith { id -> NodeId(id.value.substringBefore('$')).takeIf { it in protected } ?: id }
            val nodes=raw.nodes.values.map { n -> when(n) {
                is LiteralNode -> n.copy(id=names.getValue(n.id))
                is UnaryNode -> n.copy(id=names.getValue(n.id),child=names.getValue(n.child))
                is BinaryNode -> n.copy(id=names.getValue(n.id),left=names.getValue(n.left),right=names.getValue(n.right))
            } }
            val dag=FormulaDag(names.getValue(raw.root),nodes)
            directory.resolve("candidate_bound_$bound.txt").writeText(FormulaDagRenderer.render(dag)+"\n")
            val kept=solution.eval(CompUtil.parseOneExpression_fromString(world,"#experimentKept")).toString().toInt()
            val size=solution.eval(CompUtil.parseOneExpression_fromString(world,"#experimentReach")).toString().toInt()
            check(size==dag.size())
            decodeNanos+=System.nanoTime()-decode
            val verify=System.nanoTime(); verify(dag,kept); verifyNanos+=System.nanoTime()-verify
            return dag to kept
        }
        var scope=minOf(plan.nodeBudget,8)
        var best:Pair<FormulaDag,Int>?=null
        var passes=0
        if(repair==null) {
            while(true) {
                best=execute(0,scope);passes++
                if(best!=null||scope==plan.nodeBudget) break
                scope=minOf(plan.nodeBudget,scope*2)
            }
        } else {
            while(true) {
                best=execute(repair.oldEdges.size,scope);passes++
                if(best!=null||scope==plan.nodeBudget) break
                scope=minOf(plan.nodeBudget,scope*2)
            }
            if(best==null) { best=execute(0,scope);passes++ }
        }
        if(best!=null && repair!=null && best.second<repair.oldEdges.size) {
            var low=best.second; var high=repair.oldEdges.size
            while(low<high) {
                val mid=low+(high-low+1)/2; val candidate=execute(mid,scope);passes++
                if(candidate==null) high=mid-1 else { check(candidate.second>=mid);low=candidate.second;best=candidate }
            }
        }
        val metadata=linkedMapOf<String,Any>("solverMode" to "ATLAS_B", "solverStatus" to if(best==null) "UNSAT" else "OPTIMAL",
            "nodeBudget" to plan.nodeBudget,"binaryBudget" to plan.binaryBudget,"protectedCount" to plan.protectedIdentities.size,
            "searchNodeUniverse" to scope+task.literals.size+plan.protectedIdentities.count { it.label !is MacroLabel.Literal },
            "costScope" to scope,"expandedNodeCount" to (best?.first?.size() ?: 0),
            "objectivePrimary" to (best?.second ?: 0),"objectiveSecondary" to (best?.first?.size() ?: 0),
            "modelBytes" to modelBytes,"optimizationPasses" to passes,"encodingSec" to encodingNanos/1e9,"solverSec" to solverNanos/1e9,
            "decodeSec" to decodeNanos/1e9,"verifySec" to verifyNanos/1e9)
        directory.resolve("verification.json").writeText(metadataJson(mapOf("status" to if(best==null) "NOT_APPLICABLE_UNSAT" else "PASSED")))
        return MacroSolveResult(best?.first,null,metadata)
    }

    private fun verify(dag: FormulaDag, kept: Int) {
        try {
            check(dag.size()<=plan.nodeBudget && dag.nodes.values.count { it is BinaryNode }<=plan.binaryBudget)
            check(plan.automaton.isAccepting(DagConstraintEvaluator(plan.automaton).evaluate(dag).rootState))
            for(c in plan.identityConstraints) check(when(c) {
                is MacroIdentityConstraint.NamedRoot -> dag.root==c.target
                is MacroIdentityConstraint.NamedDirectChild -> when(val n=dag.node(c.source)) {
                    is UnaryNode -> c.port==PortKind.CHILD && n.child==c.target
                    is BinaryNode -> (if(c.port==PortKind.LEFT)n.left else n.right)==c.target
                    else -> false
                }
                is MacroIdentityConstraint.NamedReachability -> {
                    val seen=hashSetOf<NodeId>();fun walk(id:NodeId) { dag.children(id).forEach { if(seen.add(it)) walk(it) } }
                    walk(c.source);c.target in seen
                }
                is MacroIdentityConstraint.NoDAGReuse -> dag.nodes.values.all { (c.excludeLiterals && it is LiteralNode)||dag.parents(it.id).size<=1 }
                MacroIdentityConstraint.NoSharedLiteralBranches -> {
                    fun literalsBelow(start:NodeId):Set<NodeId> {
                        val seen=hashSetOf<NodeId>();fun walk(id:NodeId) { if(seen.add(id))dag.children(id).forEach(::walk) }
                        walk(start);return seen.filter { dag.node(it) is LiteralNode }.toSet()
                    }
                    dag.nodes.values.filterIsInstance<BinaryNode>().all { literalsBelow(it.left).intersect(literalsBelow(it.right)).isEmpty() }
                }
                MacroIdentityConstraint.LeftNotEqualRight -> dag.nodes.values.filterIsInstance<BinaryNode>().all { it.left!=it.right }
            })
            check(kept==(repair?.oldEdges?.count { it.source in dag.nodes && it.target in dag.children(it.source) } ?: 0))
            for((positive,traces) in listOf(true to task.positiveExamples,false to task.negativeExamples))
                for(t in traces) check(ConcreteLassoEvaluator.values(dag,t).getValue(dag.root)[0]==positive) {
                    "Trace classification failed: ${FormulaDagRenderer.render(dag)}, expected=$positive, trace=$t"
                }
            val macro=FiberMacroCanonicalizer.canonicalize(AnchorExtractor.extract(MacroEligibilityAnalyzer(plan.automaton).analyze(
                dag,plan.protectedIdentities.map { it.id },plan.allowedUnaryOperators)))
            check(MacroRoundTripVerifier.verify(dag,macro).isValid)
        } catch(e:Exception) { throw MacroVerificationException(e) }
    }
}
