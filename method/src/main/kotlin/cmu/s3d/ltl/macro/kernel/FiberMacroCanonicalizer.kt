package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.fiber.FiberTable
import cmu.s3d.ltl.macro.unary.UnaryNormalizer

/** Canonicalize only through complete Phase 1 fibers, never through semantic type alone. */
object FiberMacroCanonicalizer {
    /** Reuse the exact automaton instance that computed target states (including product ownership). */
    fun <Q : Any> canonicalize(raw: RawMacroDag<Q>): MacroDag<Q> {
        val automaton = raw.eligibility.automaton
        val states = raw.edgesByPort.values.map { raw.evaluation.stateByNode.getValue(it.target) }.distinct()
        val table = FiberTable(automaton, states, raw.statistics.maxOriginalUnaryLength, raw.allowedUnaryOperators)
        val edges = raw.edgesByPort.mapValues { (port, edge) ->
            val qIn = raw.evaluation.stateByNode.getValue(edge.target)
            val key = table.replay(qIn, edge.originalWord)
            val expectedQOut = raw.evaluation.stateByNode.getValue(immediateChild(raw.originalDag, port))
            check(key.qOut == expectedQOut) { "Original port state disagrees with replay at $port" }
            val representative = checkNotNull(table[key]) { "Missing bounded fiber at $port: $key" }.word
            check(representative.length <= edge.originalWord.length)
            check(UnaryNormalizer.normalize(representative) == key.semanticType)
            check(representative.isEmpty() == !key.nonEmpty)
            check(table.replay(qIn, representative) == key)
            CanonicalMacroEdge(edge, key, representative)
        }
        return MacroDag(raw.actualAnchors, edges, raw.protectedNodeIds, raw.originalDag.size(),
            raw.evaluation.rootState, raw.allowedUnaryOperators, automaton).also {
            it.statistics.validatePortBudget()
            check(it.statistics.canonicalNodeCount <= it.originalNodeCount)
        }
    }
}
