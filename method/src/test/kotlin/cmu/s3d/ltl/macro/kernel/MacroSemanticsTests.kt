package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.State
import cmu.s3d.ltl.macro.analysis.MacroEligibilityAnalyzer
import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.samples2ltl.TaskParser
import org.junit.jupiter.api.Test
import kotlin.random.Random
import kotlin.test.*

class MacroSemanticsTests {
    private fun profiles(): List<ConstraintAutomaton<*>> = listOf(
        NnfAutomaton(), CnfAutomaton(), DnfAutomaton(), PropositionalAutomaton(), RequiredPropositionAutomaton("p"),
        ProductConstraintAutomaton(listOf(NnfAutomaton(), RequiredPropositionAutomaton("p"), PropositionalAutomaton()))
    )

    // Star-projected automata are captured by this generic helper; product instances
    // stay the same across evaluation, canonicalization and production verification.
    private fun <Q : Any> canonical(dag: FormulaDag, profile: ConstraintAutomaton<Q>, protected: Set<NodeId>): FormulaDag {
        val macro = FiberMacroCanonicalizer.canonicalize(AnchorExtractor.extract(MacroEligibilityAnalyzer(profile).analyze(dag, protected)))
        val verified = MacroRoundTripVerifier.verify(dag, macro)
        assertTrue(verified.isValid, "${verified.violations}\n$dag")
        assertTrue(macro.statistics.numberOfPorts <= macro.statistics.p + 3 * macro.statistics.b + 2)
        val interiors = macro.edgesByPort.values.flatMap { it.originalInternalNodeIds }
        assertEquals(interiors.size, interiors.distinct().size)
        assertEquals(dag.nodes.keys - macro.actualAnchors.keys, interiors.toSet())
        assertEquals(dag, MacroDagExpander.expandOriginal(macro))
        return assertNotNull(verified.canonicalDag)
    }

    @Test
    fun exhaustiveSmallDagProtectedSubsetProfileAndLassoCombinationsPreserveEveryRootPosition() {
        val dags = smallDags()
        val lassos = smallLassos()
        assertEquals(60, dags.size)
        assertEquals(36, lassos.size)
        var roundTrips = 0
        var truthComparisons = 0
        for (dag in dags) {
            val ids = dag.nodes.keys.toList()
            val truths = lassos.map { UFreeLassoOracle.evaluate(dag, it) }
            for (mask in 0 until (1 shl ids.size)) {
                val protected = ids.filterIndexed { i, _ -> mask and (1 shl i) != 0 }.toSet()
                for (profile in profiles()) {
                    val transformed = canonical(dag, profile, protected)
                    roundTrips++
                    for ((i, trace) in lassos.withIndex()) {
                        assertContentEquals(truths[i], UFreeLassoOracle.evaluate(transformed, trace),
                            "exhaustive DAG=$dag protected=$protected profile=${profile.javaClass.simpleName} lasso=$trace")
                        truthComparisons++
                    }
                }
            }
        }
        assertEquals(2616, roundTrips)
        assertEquals(94176, truthComparisons)
        println("Phase 2 exhaustive: 60 DAGs, 36 lassos, 2616 round trips, 94176 root-vector comparisons")
    }

    // All tree formulas of syntax size <= 3 over {p,q}, four unary and three Boolean
    // binary operators, plus each Boolean root sharing one F/G unary child.
    private fun smallDags(): List<FormulaDag> {
        val result = ArrayList<FormulaDag>()
        for (name in listOf("p", "q")) {
            TestDags().let { result.add(it.dag(it.atom(name))) }
            for (outer in UnaryOperator.values()) {
                TestDags().let { result.add(it.dag(it.unary(outer, it.atom(name)))) }
                for (inner in UnaryOperator.values()) TestDags().let {
                    result.add(it.dag(it.unary(outer, it.unary(inner, it.atom(name)))))
                }
            }
        }
        for (operator in listOf(BinaryOperator.AND, BinaryOperator.OR, BinaryOperator.IMPLIES)) {
            for (left in listOf("p", "q")) for (right in listOf("p", "q")) TestDags().let {
                result.add(it.dag(it.binary(operator, it.atom(left), it.atom(right))))
            }
            for (unary in listOf(UnaryOperator.F, UnaryOperator.G)) TestDags().let {
                val shared = it.unary(unary, it.atom("p"))
                result.add(it.dag(it.binary(operator, shared, shared)))
            }
        }
        return result
    }

    // All loop starts and both propositions' valuations for lasso lengths 1 and 2.
    private fun smallLassos(): List<LassoTrace> {
        val result = ArrayList<LassoTrace>()
        for (length in 1..2) for (loopStart in 0 until length) for (mask in 0 until (1 shl (2 * length))) {
            val states = (0 until length).map { i -> State(mapOf(
                "p" to (mask and (1 shl (2 * i)) != 0), "q" to (mask and (1 shl (2 * i + 1)) != 0)
            )) }
            result.add(LassoTrace(states.take(loopStart), states.drop(loopStart)))
        }
        return result
    }

    @Test
    fun seededRandomDagSharingProtectedSubsetsAndAllProfilesPreserveSemantics() {
        val seed = 20260921
        val random = Random(seed)
        val profiles = profiles()
        var sharingCases = 0
        var protectedCases = 0
        var reductions = 0
        repeat(1200) { iteration ->
            val b = TestDags()
            b.atom("p")
            b.atom("q")
            repeat(random.nextInt(3, 25)) {
                val available = b.nodes.keys.toList()
                if (random.nextInt(3) != 0) {
                    b.unary(UnaryOperator.values()[random.nextInt(4)], available[random.nextInt(available.size)])
                } else {
                    val left = available[random.nextInt(available.size)]
                    val right = if (random.nextBoolean()) left else available[random.nextInt(available.size)]
                    b.binary(listOf(BinaryOperator.AND, BinaryOperator.OR, BinaryOperator.IMPLIES)[random.nextInt(3)], left, right)
                }
            }
            // Select the reachable generated subgraph before constructing the strict DAG.
            // This is fixture generation, not production normalization dropping nodes.
            val root = b.nodes.keys.last()
            val reachable = linkedSetOf(root)
            val pending = java.util.ArrayDeque<NodeId>()
            pending.add(root)
            while (pending.isNotEmpty()) for (child in b.nodes.getValue(pending.removeFirst()).children()) {
                if (reachable.add(child)) pending.addLast(child)
            }
            val dag = FormulaDag(root, b.nodes.filterKeys { it in reachable }.values.shuffled(random).associateBy { it.id })
            val protected = dag.nodes.keys.filter { random.nextInt(4) == 0 }.toSet()
            if (dag.nodes.keys.any { dag.indegree(it) > 1 }) sharingCases++
            if (protected.isNotEmpty()) protectedCases++
            val states = List(random.nextInt(1, 13)) { State(mapOf("p" to random.nextBoolean(), "q" to random.nextBoolean())) }
            val loopStart = random.nextInt(states.size)
            val lasso = LassoTrace(states.take(loopStart), states.drop(loopStart))
            try {
                val transformed = canonical(dag, profiles[iteration % profiles.size], protected)
                if (transformed.size() < dag.size()) reductions++
                assertContentEquals(UFreeLassoOracle.evaluate(dag, lasso), UFreeLassoOracle.evaluate(transformed, lasso))
                val originalOrder = FormulaDag(dag.root, dag.nodes.values.toList().asReversed().associateBy { it.id })
                assertEquals(transformed, canonical(originalOrder, profiles[iteration % profiles.size], protected))
            } catch (failure: AssertionError) {
                throw AssertionError("seed=$seed iteration=$iteration protected=$protected lasso=$lasso DAG=$dag", failure)
            } catch (failure: Exception) {
                throw AssertionError("seed=$seed iteration=$iteration protected=$protected lasso=$lasso DAG=$dag", failure)
            }
        }
        assertTrue(sharingCases >= 100, "sharingCases=$sharingCases")
        assertTrue(protectedCases >= 100, "protectedCases=$protectedCases")
        assertTrue(reductions > 0)
        println("Phase 2 random: seed=$seed, 1200 cases; sharing=$sharingCases protected=$protectedCases reductions=$reductions")
    }

    @Test
    fun oracleHandlesInfiniteLoopsAllOperatorsAndEveryPositionIndependently() {
        val trace = LassoTrace(listOf(State(mapOf("p" to true))), listOf(State(mapOf("p" to false))))
        for ((w, expected) in listOf(
            "" to booleanArrayOf(true, false), "X" to booleanArrayOf(false, false),
            "F" to booleanArrayOf(true, false), "G" to booleanArrayOf(false, false),
            "!" to booleanArrayOf(false, true)
        )) {
            val b = TestDags()
            assertContentEquals(expected, UFreeLassoOracle.evaluate(b.dag(b.chain(w, b.atom())), trace))
        }
        val looping = LassoTrace(loop = listOf(State(mapOf("p" to false)), State(mapOf("p" to true))))
        for (w in listOf("F", "GF")) {
            val b = TestDags()
            assertContentEquals(booleanArrayOf(true, true), UFreeLassoOracle.evaluate(b.dag(b.chain(w, b.atom())), looping))
        }
        for (operator in listOf(BinaryOperator.AND, BinaryOperator.OR, BinaryOperator.IMPLIES)) {
            val b = TestDags()
            val p = b.atom()
            val dag = b.dag(b.binary(operator, p, b.chain("!", p)))
            val expected = when (operator) {
                BinaryOperator.AND -> booleanArrayOf(false, false)
                BinaryOperator.OR -> booleanArrayOf(true, true)
                else -> booleanArrayOf(false, true)
            }
            assertContentEquals(expected, UFreeLassoOracle.evaluate(dag, trace))
        }
    }

    @Test
    fun extractedSampleRetainsPositiveAndNegativeTraceClassification() {
        val task = TaskParser.parseTask(ClassLoader.getSystemResource("samples2ltl/example0000.trace").readText())
        val dag = AlloySolutionDagExtractor().extract(assertNotNull(task.buildLearner().learn()))
        val transformed = canonical(dag, NnfAutomaton(), emptySet())
        for ((traces, positive) in listOf(task.positiveExamples to true, task.negativeExamples to false)) {
            for (trace in traces) {
                val originalTruth = UFreeLassoOracle.evaluate(dag, trace)
                assertEquals(positive, originalTruth[0])
                assertContentEquals(originalTruth, UFreeLassoOracle.evaluate(transformed, trace))
            }
        }
    }
}
