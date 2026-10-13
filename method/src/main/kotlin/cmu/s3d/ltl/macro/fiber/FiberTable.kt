package cmu.s3d.ltl.macro.fiber

import cmu.s3d.ltl.macro.constraint.ConstraintAutomaton
import cmu.s3d.ltl.macro.unary.SemanticType
import cmu.s3d.ltl.macro.unary.UnaryNormalizer
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.macro.unary.UnaryWord
import java.util.Collections

/**
 * Bounded BFS of unary fibers, separately for each supplied input state. Callers
 * supply the child states relevant to their application (all enum values for a
 * full base automaton table, or reachable product states). This avoids requiring
 * eager enumeration of a product automaton's entire state space.
 *
 * Invalid/nonaccepting states are deliberately retained. A representative preserves
 * the full fiber; acceptance filtering belongs to the consumer, not normalization.
 */
class FiberTable<Q : Any>(
    private val automaton: ConstraintAutomaton<Q>,
    inputStates: Collection<Q>,
    val maxUnaryLength: Int,
    allowedOperators: Collection<UnaryOperator> = UnaryOperator.LEXICAL_ORDER
) {
    /** Defensive snapshot of the requested child-state domain. */
    val inputStates: Set<Q> = Collections.unmodifiableSet(LinkedHashSet(inputStates))

    /** Unique allowed operators in the fixed order ! < X < F < G. */
    val allowedOperators: List<UnaryOperator> = Collections.unmodifiableList(
        allowedOperators.distinct().sortedBy { it.lexicalRank }
    )

    /** Complete immutable key-to-witness mapping. */
    val entries: Map<FiberKey<Q>, FiberRepresentative>

    init {
        require(maxUnaryLength >= 0) { "maxUnaryLength must be nonnegative" }
        entries = Collections.unmodifiableMap(build())
    }

    /** Return the witness, or null for a fiber outside this bounded table. */
    operator fun get(key: FiberKey<Q>): FiberRepresentative? = entries[key]

    /** Immutable view of all generated keys. */
    fun keys(): Set<FiberKey<Q>> = entries.keys

    /** Number of distinct fibers, including empty words for supplied input states. */
    fun size(): Int = entries.size

    /**
     * Replay any U-free word, even outside this table's bound/alphabet/domain.
     * [F, X, G] executes G, then X, then F from qIn. This is a classification
     * utility; get(replay(...)) can be null when the fiber is not in the table.
     */
    fun replay(qIn: Q, word: UnaryWord): FiberKey<Q> {
        var qOut = qIn
        for (operator in word.operators.asReversed()) qOut = automaton.unaryState(operator, qOut)
        return FiberKey(qIn, UnaryNormalizer.normalize(word), !word.isEmpty(), qOut)
    }

    private fun build(): LinkedHashMap<FiberKey<Q>, FiberRepresentative> {
        val result = LinkedHashMap<FiberKey<Q>, FiberRepresentative>()
        for (qIn in inputStates) {
            val initial = FiberKey(qIn, SemanticType.IDENTITY, false, qIn)
            val empty = FiberRepresentative(UnaryWord.EMPTY)
            result[initial] = empty
            var frontier = linkedMapOf(initial to empty)
            var depth = 0
            while (depth < maxUnaryLength && frontier.isNotEmpty()) {
                val next = LinkedHashMap<FiberKey<Q>, FiberRepresentative>()
                for ((key, representative) in frontier) {
                    for (operator in allowedOperators) {
                        val successor = FiberKey(
                            qIn,
                            UnaryNormalizer.prefix(operator, key.semanticType),
                            true,
                            automaton.unaryState(operator, key.qOut)
                        )
                        // Already completed layers have strictly shorter witnesses.
                        if (successor in result) continue
                        val candidate = representative.word.prepend(operator)
                        val previous = next[successor]
                        if (previous == null || candidate < previous.word) {
                            next[successor] = FiberRepresentative(candidate)
                        }
                    }
                }
                // Prepending does NOT make ordinary queue discovery lexicographic.
                // Finish all equal-length tie comparisons before expanding this layer.
                // Discarded witnesses are safe: identical keys have identical future
                // transitions, and the same prefix preserves length and lexical order.
                result.putAll(next)
                frontier = next
                depth++
            }
        }
        return result
    }
}
