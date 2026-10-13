package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator

/**
 * Exact congruence quotient of a finite deterministic bottom-up tree automaton.
 * Two states are merged only when no context over the configured alphabet can
 * distinguish their acceptance.  This reduces both the fiber domain and the
 * quadratic binary-transition part of the Alloy encoding.
 */
class MinimizedConstraintAutomaton<Q : Any>(
    private val base: ConstraintAutomaton<Q>,
    propositions: Collection<String>,
    private val unaryOperators: List<UnaryOperator>,
    private val binaryOperators: List<BinaryOperator>
) : ConstraintAutomaton<Int> {
    private val literalClasses: Map<String, Int>
    private val unaryTransitions: Map<Pair<UnaryOperator, Int>, Int>
    private val binaryTransitions: Map<Triple<BinaryOperator, Int, Int>, Int>
    private val accepting: Set<Int>
    val rawStateCount: Int
    val stateCount: Int

    init {
        val raw = LinkedHashSet<Q>()
        propositions.forEach { raw.add(base.literalState(it)) }
        do {
            val previous = raw.toList()
            for (q in previous) for (op in unaryOperators) raw.add(base.unaryState(op, q))
            for (left in previous) for (right in previous) for (op in binaryOperators)
                raw.add(base.binaryState(op, left, right))
        } while (raw.size != previous.size)
        val states = raw.toList()
        val rawId = states.withIndex().associate { it.value to it.index }
        rawStateCount = states.size
        fun id(q: Q) = rawId.getValue(q)

        var partition = IntArray(states.size) { if (base.isAccepting(states[it])) 1 else 0 }
        while (true) {
            val classes = linkedMapOf<List<Int>, Int>()
            val refined = IntArray(states.size)
            for ((i, q) in states.withIndex()) {
                val signature = arrayListOf(if (base.isAccepting(q)) 1 else 0)
                unaryOperators.forEach { signature.add(partition[id(base.unaryState(it, q))]) }
                for (op in binaryOperators) for (other in states) {
                    signature.add(partition[id(base.binaryState(op, q, other))])
                    signature.add(partition[id(base.binaryState(op, other, q))])
                }
                refined[i] = classes.getOrPut(signature) { classes.size }
            }
            if (refined.contentEquals(partition)) break
            partition = refined
        }
        stateCount = (partition.maxOrNull() ?: -1) + 1
        val representatives = (0 until stateCount).map { c -> states[partition.indexOf(c)] }
        literalClasses = propositions.distinct().associateWith { partition[id(base.literalState(it))] }
        unaryTransitions = buildMap {
            for (c in representatives.indices) for (op in unaryOperators)
                put(op to c, partition[id(base.unaryState(op, representatives[c]))])
        }
        binaryTransitions = buildMap {
            for (left in representatives.indices) for (right in representatives.indices) for (op in binaryOperators)
                put(Triple(op, left, right), partition[id(base.binaryState(op, representatives[left], representatives[right]))])
        }
        accepting = representatives.indices.filter { base.isAccepting(representatives[it]) }.toSet()
    }

    override fun literalState(proposition: String) = literalClasses.getValue(proposition)
    override fun unaryState(operator: UnaryOperator, child: Int) = unaryTransitions.getValue(operator to child)
    override fun binaryState(operator: BinaryOperator, left: Int, right: Int) =
        binaryTransitions.getValue(Triple(operator, left, right))
    override fun isAccepting(state: Int) = state in accepting
}
