package cmu.s3d.ltl.macro.constraint

import java.util.Collections

/** Immutable heterogeneous tuple, owned and interned by one product automaton. */
class ProductState internal constructor(internal val owner: Any, components: List<Any>) {
    /** Unmodifiable component states in the automata's declared order. */
    val components: List<Any> = Collections.unmodifiableList(ArrayList(components))

    /** States in different product domains cannot accidentally be interchanged. */
    override fun equals(other: Any?): Boolean =
        other is ProductState && owner === other.owner && components == other.components

    /** Hash both the state domain and the tuple contents. */
    override fun hashCode(): Int = 31 * System.identityHashCode(owner) + components.hashCode()

    /** Render the tuple in component order. */
    override fun toString(): String = components.joinToString(prefix = "(", postfix = ")")
}
