package cmu.s3d.ltl.macro.unary

import java.util.Collections

/**
 * Immutable outer-to-inner word: [F, X, G] means F(X(G(hole))).
 * Bottom-up evaluation therefore visits the operators in reverse order.
 */
class UnaryWord(operators: Collection<UnaryOperator>) : Iterable<UnaryOperator>, Comparable<UnaryWord> {
    /** Defensive, unmodifiable snapshot in outer-to-inner order. */
    val operators: List<UnaryOperator> = Collections.unmodifiableList(ArrayList(operators))

    /** Construct an outer-to-inner word directly from operators. */
    constructor(vararg operators: UnaryOperator) : this(operators.toList())

    /** Number of unary operators. */
    val length: Int get() = operators.size

    /** Whether this is the identity context with no syntax nodes. */
    fun isEmpty(): Boolean = operators.isEmpty()

    /** Add an operator outside this entire context. */
    fun prepend(operator: UnaryOperator): UnaryWord = UnaryWord(listOf(operator) + operators)

    /** Visit outermost to innermost; use operators.asReversed() for bottom-up replay. */
    override fun iterator(): Iterator<UnaryOperator> = operators.iterator()

    /** Lexicographic comparison under ! < X < F < G (length is not the primary key). */
    override fun compareTo(other: UnaryWord): Int {
        for (i in 0 until minOf(length, other.length)) {
            val comparison = operators[i].lexicalRank.compareTo(other.operators[i].lexicalRank)
            if (comparison != 0) return comparison
        }
        return length.compareTo(other.length)
    }

    /** Equality of the complete syntax word. */
    override fun equals(other: Any?): Boolean = other is UnaryWord && operators == other.operators

    /** Content hash suitable for immutable map keys. */
    override fun hashCode(): Int = operators.hashCode()

    /** Compact outer-to-inner symbols; the empty word prints as an empty string. */
    override fun toString(): String = operators.joinToString("") { it.symbol }

    companion object {
        /** The empty word, distinct from nonempty semantic identities such as !!. */
        val EMPTY = UnaryWord(emptyList())
    }
}
