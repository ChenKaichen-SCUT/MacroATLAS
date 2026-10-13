package cmu.s3d.ltl.macro.constraint

import cmu.s3d.ltl.macro.unary.UnaryOperator
import java.util.concurrent.ConcurrentHashMap

/**
 * Lazy conjunction of any number of constraint automata, including zero (accept all).
 * Only tuples reached by actual transitions are allocated; no Cartesian state space
 * is enumerated. The interning cache is private; logical states remain immutable.
 */
class ProductConstraintAutomaton(automata: List<ConstraintAutomaton<*>>) : ConstraintAutomaton<ProductState> {
    private val owner = Any()

    // Type erasure is confined here. Tuple construction is private to this automaton,
    // and ownership checks ensure component i is always fed to its own automaton.
    @Suppress("UNCHECKED_CAST")
    private val components = automata.map { it as ConstraintAutomaton<Any> }
    private val states = ConcurrentHashMap<ProductState, ProductState>()

    /** Number of tuples reached so far, useful for checking lazy construction. */
    val internedStateCount: Int get() = states.size

    private fun intern(values: List<Any>): ProductState {
        val candidate = ProductState(owner, values)
        return states.putIfAbsent(candidate, candidate) ?: candidate
    }

    private fun validate(state: ProductState) {
        require(state.owner === owner) { "Product state belongs to a different automaton" }
    }

    /** Apply each component's literal transition and intern the resulting tuple. */
    override fun literalState(proposition: String): ProductState =
        intern(components.map { it.literalState(proposition) })

    /** Apply unary transitions component-wise. */
    override fun unaryState(operator: UnaryOperator, child: ProductState): ProductState {
        validate(child)
        return intern(components.mapIndexed { i, automaton -> automaton.unaryState(operator, child.components[i]) })
    }

    /** Apply binary transitions component-wise, retaining child order. */
    override fun binaryState(operator: BinaryOperator, left: ProductState, right: ProductState): ProductState {
        validate(left)
        validate(right)
        return intern(components.mapIndexed { i, automaton ->
            automaton.binaryState(operator, left.components[i], right.components[i])
        })
    }

    /** Accept iff every component accepts; the empty product accepts vacuously. */
    override fun isAccepting(state: ProductState): Boolean {
        validate(state)
        return components.withIndex().all { (i, automaton) -> automaton.isAccepting(state.components[i]) }
    }
}
