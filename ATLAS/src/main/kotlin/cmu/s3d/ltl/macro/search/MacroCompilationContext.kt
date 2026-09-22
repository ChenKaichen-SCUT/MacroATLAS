package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.LassoTrace
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
class FiberCatalog<Q : Any>(registry: ConstraintStateRegistry<Q>) {
    val entries: List<CatalogEntry<Q>>
    init {
        val plan = registry.plan
        val table = FiberTable(plan.automaton, registry.states, plan.nodeBudget, plan.allowedUnaryOperators)
        val ordered = table.entries.entries.sortedWith(compareBy(
            { registry.stateId(it.key.qIn) }, { it.key.semanticType.xCount },
            { it.key.semanticType.tail.ordinal }, { it.key.semanticType.negated },
            { it.key.nonEmpty }, { registry.stateId(it.key.qOut) }
        ))
        entries = immutableList(ordered.mapIndexed { i, e ->
            CatalogEntry(i, e.key, registry.stateId(e.key.qIn), registry.stateId(e.key.qOut), e.value.word)
        })
    }
}

/** Precise successor/future sets, including a nonempty loop. Precomputed once per task. */
class LassoPositions(val trace: LassoTrace, maxShift: Int) {
    val successor: List<Int>
    val future: List<List<Int>>
    val succPow: List<List<Int>>
    init {
        require(trace.loop.isNotEmpty()) { "Macro semantics requires a nonempty lasso loop" }
        successor = (0 until trace.length()).map { if (it + 1 == trace.length()) trace.prefix.size else it + 1 }
        future = successor.indices.map { start ->
            val seen = LinkedHashSet<Int>(); var i = start
            while (seen.add(i)) i = successor[i]
            seen.toList()
        }
        val shifts = arrayListOf(successor.indices.toList())
        repeat(maxShift) { shifts.add(shifts.last().map { successor[it] }) }
        succPow = shifts
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
    val positives = immutableList(positives)
    val negatives = immutableList(negatives)
    val registry = ConstraintStateRegistry(plan)
    val catalog = FiberCatalog(registry)
    val positions = (positives + negatives).map { LassoPositions(it, plan.nodeBudget) }
    init { require(positions.all { p -> p.trace.getTrace().all { it.values.keys.containsAll(plan.propositions) } }) }
}
