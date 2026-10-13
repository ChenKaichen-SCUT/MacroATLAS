package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.macro.constraint.MinimizedConstraintAutomaton
import cmu.s3d.ltl.macro.constraint.NeutralProfileAutomaton
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.samples2ltl.TaskParser
import org.junit.jupiter.api.Test
import kotlin.test.*

class NeutralProfileExperimentTest {
    private fun <Q : Any> checkStates(plan: MacroConstraintPlan<Q>, q: Int) {
        val registry = ConstraintStateRegistry(plan)
        assertEquals(q, registry.states.size)
        assertTrue(registry.states.all { plan.automaton.isAccepting(it) })
    }

    private fun task(marker: String) = TaskParser.parseTask("""
        0;0;1;0::3
        ---
        0;0;0;0::3
        ---
        X
        ---
        [16]
        ---
        X(X(x0))
        ---
        $marker
    """.trimIndent())

    @Test
    fun exactMarkerPreservesAllNeutralStatesWithoutChangingAcceptance() {
        for (q in listOf(1, 2, 4, 8, 16)) {
            val result = assertIs<MacroTaskAnalysis.Supported>(
                RecognizedConstraintAnalyzer.analyze(task("// RQ4_NEUTRAL_PROFILE_STATES=$q"), 0))
            assertEquals(listOf("RQ4NeutralProfile($q)"), result.recognizedFeatures)
            checkStates(result.plan, q)
        }
        val ordinary = MinimizedConstraintAutomaton(NeutralProfileAutomaton(16),
            listOf("x0"), listOf(UnaryOperator.X), emptyList())
        assertEquals(1, ordinary.stateCount)
    }

    @Test
    fun malformedMarkerAndOtherAlphabetFailClosed() {
        assertIs<MacroTaskAnalysis.Unsupported>(RecognizedConstraintAnalyzer.analyze(
            task("// RQ4_NEUTRAL_PROFILE_STATES=3"), 0))
        assertIs<MacroTaskAnalysis.Unsupported>(RecognizedConstraintAnalyzer.analyze(
            task("// RQ4_NEUTRAL_PROFILE_STATES=16"), 1, 10))
    }

    @Test
    fun neutralProfileStillLearnsTheSameSmallFormula() {
        val example = TaskParser.parseTask("""
            0;1;0::2
            ---
            0;0;0::2
            ---
            X
            ---
            [2]
            ---
            X(x0)
            ---
            // RQ4_NEUTRAL_PROFILE_STATES=2
        """.trimIndent())
        val result = assertIs<MacroTaskAnalysis.Supported>(
            RecognizedConstraintAnalyzer.analyze(example, 0))
        fun <Q : Any> solve(plan: MacroConstraintPlan<Q>) =
            MacroLearner(plan, example.positiveExamples, example.negativeExamples).solve()
        val answer = solve(result.plan)
        assertEquals(2, answer.dag?.size())
        assertEquals(2, answer.metadata["constraintStateCount"])
    }
}
