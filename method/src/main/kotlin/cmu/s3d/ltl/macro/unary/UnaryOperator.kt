package cmu.s3d.ltl.macro.unary

import java.util.Collections

/** U-free unary operators, with ATLAS task symbols and Alloy signature names. */
enum class UnaryOperator(val symbol: String, val atlasName: String, val lexicalRank: Int) {
    NOT("!", "Neg", 0),
    X("X", "X", 1),
    F("F", "F", 2),
    G("G", "G", 3);

    companion object {
        /** Explicit outer-to-inner lexicographic order: ! < X < F < G. */
        val LEXICAL_ORDER: List<UnaryOperator> = Collections.unmodifiableList(
            values().sortedBy { it.lexicalRank }
        )

        /** Adapt one ATLAS symbol/signature; binary U/Until is deliberately rejected. */
        fun fromAtlas(operator: String): UnaryOperator = values().firstOrNull {
            it.symbol == operator || it.atlasName == operator
        } ?: throw IllegalArgumentException("Not a U-free unary operator: $operator")
    }
}
