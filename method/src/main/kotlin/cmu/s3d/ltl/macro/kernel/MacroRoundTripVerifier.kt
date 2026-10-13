package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.analysis.DagConstraintEvaluation
import cmu.s3d.ltl.macro.analysis.DagConstraintEvaluator
import cmu.s3d.ltl.macro.analysis.MacroEligibilityAnalyzer
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.fiber.FiberTable

/** An immutable, machine-readable failure in a macro compression/reconstruction invariant. */
data class MacroViolation(val code: Code, val message: String, val port: MacroPort? = null) {
    /** Stable diagnostic categories for future solver/compiler debugging. */
    enum class Code {
        ORIGINAL_EXPANSION, CANONICAL_STRUCTURE, ANCHOR_IDENTITY, PROTECTED_IDENTITY,
        FIBER_REPLAY, PORT_STATE, ROOT_STATE, ACCEPTANCE, NODE_COUNT, SKELETON_OR_FIBER,
        PROFILE, KERNEL_BUDGET, REPRESENTATIVE
    }
}

/** Validation result and the successfully reconstructed canonical graph, if structurally valid. */
class MacroVerificationResult(violations: Collection<MacroViolation>, val canonicalDag: FormulaDag?) {
    /** Every observed failure; callers need not parse exception messages to distinguish categories. */
    val violations: List<MacroViolation> = immutableList(violations)
    /** True only when every structural, state, fiber and identity check passed. */
    val isValid: Boolean get() = violations.isEmpty()
}

/** Production round-trip oracle. Independent infinite-lasso truth checking lives only in tests. */
object MacroRoundTripVerifier {
    /** Verify a macro against its original graph, returning diagnostics instead of failing at the first violation. */
    fun <Q : Any> verify(original: FormulaDag, macro: MacroDag<Q>): MacroVerificationResult {
        val failures = ArrayList<MacroViolation>()
        fun fail(code: MacroViolation.Code, message: String, port: MacroPort? = null) {
            failures.add(MacroViolation(code, message, port))
        }
        fun guarded(code: MacroViolation.Code, action: () -> Unit) {
            try { action() } catch (e: Exception) { fail(code, "${e.javaClass.simpleName}: ${e.message}") }
        }
        guarded(MacroViolation.Code.ORIGINAL_EXPANSION) {
            if (MacroDagExpander.expandOriginal(macro) != original)
                fail(MacroViolation.Code.ORIGINAL_EXPANSION, "Original IDs, labels, children or root differ")
        }
        var canonical: FormulaDag? = null
        guarded(MacroViolation.Code.CANONICAL_STRUCTURE) {
            canonical = MacroDagExpander.expandCanonical(macro)
            FormulaDagValidator.validate(checkNotNull(canonical))
        }
        for ((id, anchor) in macro.actualAnchors) {
            val before = original.nodes[id]
            val after = canonical?.nodes?.get(id)
            if (before == null || !anchor.sameIdentityAndLabel(before) ||
                (canonical != null && (after == null || !anchor.sameIdentityAndLabel(after))))
                fail(MacroViolation.Code.ANCHOR_IDENTITY, "Anchor identity/label changed: $id")
        }
        for (id in macro.protectedNodeIds) {
            if (id !in original.nodes || id !in macro.actualAnchors || (canonical != null && id !in canonical!!.nodes))
                fail(MacroViolation.Code.PROTECTED_IDENTITY, "Protected identity missing from anchors/expansion: $id")
        }
        guarded(MacroViolation.Code.KERNEL_BUDGET) { macro.statistics.validatePortBudget() }
        if (macro.originalNodeCount != original.size() || macro.statistics.canonicalNodeCount > original.size() ||
            (canonical != null && canonical!!.size() != macro.statistics.canonicalNodeCount))
            fail(MacroViolation.Code.NODE_COUNT, "Original/canonical node counts disagree or increased")

        val automaton = macro.automaton
        var before: DagConstraintEvaluation<Q>? = null
        var after: DagConstraintEvaluation<Q>? = null
        guarded(MacroViolation.Code.PROFILE) {
            before = DagConstraintEvaluator(automaton).evaluate(original)
            if (canonical != null) after = DagConstraintEvaluator(automaton).evaluate(canonical!!)
        }
        if (before != null) {
            if (before!!.rootState != macro.constraintRootState || (after != null && before!!.rootState != after!!.rootState))
                fail(MacroViolation.Code.ROOT_STATE, "Full root constraint state changed")
            if (after != null) guarded(MacroViolation.Code.ACCEPTANCE) {
                if (automaton.isAccepting(before!!.rootState) != automaton.isAccepting(after!!.rootState))
                    fail(MacroViolation.Code.ACCEPTANCE, "Root accept/reject status changed")
            }
        }
        val replay = FiberTable(automaton, emptyList(), 0, macro.allowedUnaryOperators)
        for ((port, edge) in macro.edgesByPort) {
            try {
                if (edge.port != port || replay.replay(edge.fiberKey.qIn, edge.originalWord) != edge.fiberKey ||
                    replay.replay(edge.fiberKey.qIn, edge.representativeWord) != edge.fiberKey)
                    fail(MacroViolation.Code.FIBER_REPLAY, "Original or representative word does not replay to full fiber", port)
            } catch (e: Exception) {
                fail(MacroViolation.Code.FIBER_REPLAY, "Replay failed: ${e.message}", port)
            }
            if (edge.representativeWord.length > edge.originalWord.length ||
                edge.representativeWord.any { it !in macro.allowedUnaryOperators })
                fail(MacroViolation.Code.REPRESENTATIVE, "Representative length/alphabet invalid", port)
            if (before != null) try {
                if (before!!.stateByNode[edge.target] != edge.fiberKey.qIn ||
                    before!!.stateByNode[immediateChild(original, port)] != edge.fiberKey.qOut ||
                    (after != null && after!!.stateByNode[edge.target] != edge.fiberKey.qIn))
                    fail(MacroViolation.Code.PORT_STATE, "Target/port state differs from original or canonical DAG", port)
            } catch (e: Exception) { fail(MacroViolation.Code.PORT_STATE, "Invalid source/target: ${e.message}", port) }
        }

        guarded(MacroViolation.Code.SKELETON_OR_FIBER) {
            val expected = AnchorExtractor.extract(MacroEligibilityAnalyzer(automaton).analyze(
                original, macro.protectedNodeIds, macro.allowedUnaryOperators
            ))
            if (expected.actualAnchors != macro.actualAnchors ||
                expected.edgesByPort.mapValues { it.value.target } != macro.edgesByPort.mapValues { it.value.target })
                fail(MacroViolation.Code.SKELETON_OR_FIBER, "Macro skeleton differs from the original graph")
            if (canonical != null) {
                val again = FiberMacroCanonicalizer.canonicalize(AnchorExtractor.extract(MacroEligibilityAnalyzer(automaton).analyze(
                    canonical!!, macro.protectedNodeIds, macro.allowedUnaryOperators
                )))
                if (again.actualAnchors.keys != macro.actualAnchors.keys ||
                    again.edgesByPort.mapValues { it.value.target to it.value.fiberKey } !=
                    macro.edgesByPort.mapValues { it.value.target to it.value.fiberKey })
                    fail(MacroViolation.Code.SKELETON_OR_FIBER, "Canonical re-extraction changed skeleton or fiber")
                if (again.edgesByPort.mapValues { it.value.representativeWord } != macro.edgesByPort.mapValues { it.value.representativeWord })
                    fail(MacroViolation.Code.REPRESENTATIVE, "Representatives are not deterministic shortest witnesses")
            }
        }
        return MacroVerificationResult(failures, canonical)
    }
}
