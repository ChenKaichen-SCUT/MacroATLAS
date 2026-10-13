package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.State
import cmu.s3d.ltl.macro.dag.immutableList
import cmu.s3d.ltl.macro.fiber.*
import cmu.s3d.ltl.macro.unary.*

/** Reachable saturation, not a Cartesian product. The plan's automaton instance is never replaced. */
class ConstraintStateRegistry<Q : Any>(val plan: MacroConstraintPlan<Q>) {
    val states: List<Q>
    private val ids: Map<Q, Int>
    init {
        val reached = LinkedHashSet<Q>()
        plan.propositions.forEach { reached.add(plan.automaton.literalState(it)) }
        do {
            val previous = reached.toList()
            for (q in previous) for (op in plan.allowedUnaryOperators) reached.add(plan.automaton.unaryState(op, q))
            for (l in previous) for (r in previous) for (op in plan.allowedBinaryOperators)
                reached.add(plan.automaton.binaryState(op, l, r))
        } while (previous.size != reached.size)
        states = immutableList(reached)
        ids = states.withIndex().associate { it.value to it.index }
    }
    fun stateId(q: Q): Int = ids.getValue(q)
    fun literalTransition(p: String): Int = stateId(plan.automaton.literalState(p))
    fun unaryTransition(op: UnaryOperator, q: Int): Int = stateId(plan.automaton.unaryState(op, states[q]))
    fun binaryTransition(op: cmu.s3d.ltl.macro.constraint.BinaryOperator, l: Int, r: Int): Int =
        stateId(plan.automaton.binaryState(op, states[l], states[r]))
}

data class CatalogEntry<Q : Any>(val id: Int, val key: FiberKey<Q>, val qIn: Int, val qOut: Int, val word: UnaryWord) {
    val length: Int get() = word.length
}
class FiberCatalog<Q : Any>(registry: ConstraintStateRegistry<Q>, positions: List<LassoPositions> = emptyList()) {
    val entries: List<CatalogEntry<Q>>
    val unquotientedSize: Int
    init {
        val plan = registry.plan
        val table = FiberTable(plan.automaton, registry.states, plan.nodeBudget, plan.allowedUnaryOperators)
        val ordered = table.entries.entries.sortedWith(compareBy(
            { registry.stateId(it.key.qIn) }, { it.key.semanticType.xCount },
            { it.key.semanticType.tail.ordinal }, { it.key.semanticType.negated },
            { it.key.nonEmpty }, { registry.stateId(it.key.qOut) }
        ))
        unquotientedSize = ordered.size
        // On a fixed sample, different normalized unary words can induce exactly the
        // same Boolean function on every lasso while reaching the same constraint
        // state.  Longer representatives in such a class are strictly dominated by
        // the shortest one for both supported objectives.  Keep nonempty identity
        // separate because identity/sharing constraints observe that distinction.
        val shapes = positions.distinctBy { it.successor to it.loopStart }
        val selected = if (shapes.isEmpty()) ordered else ordered.groupBy { e ->
            listOf(registry.stateId(e.key.qIn), registry.stateId(e.key.qOut), e.key.nonEmpty) +
                shapes.map { it.semanticFunctionKey(e.key.semanticType) }
        }.values.map { group ->
            group.minWith(compareBy<Map.Entry<FiberKey<Q>, FiberRepresentative>>({ it.value.length }, { it.value.word }))
        }.sortedWith(compareBy(
            { registry.stateId(it.key.qIn) }, { it.key.semanticType.xCount },
            { it.key.semanticType.tail.ordinal }, { it.key.semanticType.negated },
            { it.key.nonEmpty }, { registry.stateId(it.key.qOut) }
        ))
        entries = immutableList(selected.mapIndexed { i, e ->
            CatalogEntry(i, e.key, registry.stateId(e.key.qIn), registry.stateId(e.key.qOut), e.value.word)
        })
    }
}

/** Precise successor/future sets, including a nonempty loop. Precomputed once per task. */
class LassoPositions(val trace: LassoTrace, maxShift: Int) {
    val successor: List<Int>
    val future: List<List<Int>>
    val succPow: List<List<Int>>
    val loopStart: Int
    val loopIndices: List<Int>
    init {
        require(trace.length() > 0) { "Macro semantics requires a nonempty trace" }
        // Original ATLAS interprets a finite trace by stuttering its final state.
        loopStart = if (trace.loop.isEmpty()) trace.length() - 1 else trace.prefix.size
        loopIndices = (loopStart until trace.length()).toList()
        successor = (0 until trace.length()).map { if (it + 1 == trace.length()) loopStart else it + 1 }
        future = successor.indices.map { start ->
            val seen = LinkedHashSet<Int>(); var i = start
            while (seen.add(i)) i = successor[i]
            seen.toList()
        }
        val shifts = arrayListOf(successor.indices.toList())
        repeat(maxShift) { shifts.add(shifts.last().map { successor[it] }) }
        succPow = shifts
    }

    /** Canonical truth-function descriptor, valid for every possible child valuation. */
    fun semanticFunctionKey(type: SemanticType): List<String> {
        fun aggregate(kind: String, indices: List<Int>): String {
            val sorted = indices.distinct().sorted()
            if (sorted.size == 1) return (if (kind.startsWith("NOT_")) "NOT_VALUE:" else "VALUE:") + sorted.single()
            return "$kind:${sorted.joinToString(",")}"
        }
        return successor.indices.map { i ->
            val shifted = succPow[type.xCount][i]
            when (type.tail) {
                TemporalTail.ID -> aggregate(if (type.negated) "NOT_VALUE" else "VALUE", listOf(shifted))
                TemporalTail.F -> aggregate(if (type.negated) "NOT_ALL" else "ANY", future[shifted])
                TemporalTail.G -> aggregate(if (type.negated) "NOT_ANY" else "ALL", future[shifted])
                TemporalTail.FG -> aggregate(if (type.negated) "NOT_ANY" else "ALL", loopIndices)
                TemporalTail.GF -> aggregate(if (type.negated) "NOT_ALL" else "ANY", loopIndices)
            }
        }
    }
    fun evaluate(type: SemanticType, input: BooleanArray): BooleanArray {
        require(input.size == successor.size)
        val base = BooleanArray(input.size) { input[it] xor type.negated }
        fun eventually(v: BooleanArray) = BooleanArray(v.size) { i -> future[i].any { v[it] } }
        fun globally(v: BooleanArray) = BooleanArray(v.size) { i -> future[i].all { v[it] } }
        val tail = when (type.tail) {
            TemporalTail.ID -> base
            TemporalTail.F -> eventually(base)
            TemporalTail.G -> globally(base)
            TemporalTail.FG -> eventually(globally(base))
            TemporalTail.GF -> globally(eventually(base))
        }
        return BooleanArray(input.size) { tail[succPow[type.xCount][it]] }
    }
}

class MacroCompilationContext<Q : Any>(val plan: MacroConstraintPlan<Q>, positives: List<LassoTrace>, negatives: List<LassoTrace>) {
    val originalPositives = immutableList(positives)
    val originalNegatives = immutableList(negatives)
    /** Exact ultimately-periodic-word canonicalization; samples with the same infinite
     * word have identical LTL semantics at position zero and need one constraint only. */
    private fun canonical(trace: LassoTrace): LassoTrace {
        require(trace.length() > 0)
        val word = trace.getTrace().map { state ->
            State(plan.propositions.associateWith { state.values[it] == true })
        }
        val loopStart = if (trace.loop.isEmpty()) word.size - 1 else trace.prefix.size
        val prefix = word.take(loopStart).toMutableList()
        var loop = word.drop(loopStart)
        for (period in 1..loop.size) if (loop.size % period == 0 && loop.indices.all { loop[it] == loop[it % period] }) {
            loop = loop.take(period); break
        }
        while (prefix.isNotEmpty() && prefix.last() == loop.last()) {
            val value = prefix.removeAt(prefix.lastIndex)
            loop = listOf(value) + loop.dropLast(1)
        }
        return LassoTrace(prefix,loop)
    }
    val positives = immutableList(positives.map(::canonical).distinct())
    val negatives = immutableList(negatives.map(::canonical).distinct())
    private val registryStart = System.nanoTime()
    val registry = ConstraintStateRegistry(plan)
    val registryNanoseconds = System.nanoTime() - registryStart
    val positions = (this.positives + this.negatives).map { LassoPositions(it, plan.nodeBudget) }
    private val fiberStart = System.nanoTime()
    val catalog = FiberCatalog(registry, positions)
    val fiberNanoseconds = System.nanoTime() - fiberStart
    // Match Original ATLAS input semantics: omitted declared values are false and
    // undeclared columns do not participate in the learned formula.
}
