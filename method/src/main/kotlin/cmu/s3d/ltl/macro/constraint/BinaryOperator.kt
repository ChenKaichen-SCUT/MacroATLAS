package cmu.s3d.ltl.macro.constraint

/** ATLAS binary operators. UNTIL is temporal and never enters unary normalization. */
enum class BinaryOperator(val symbol: String, val atlasName: String) {
    AND("&", "And"), OR("|", "Or"), IMPLIES("->", "Imply"), UNTIL("U", "Until");

    companion object {
        /** Adapt one existing ATLAS task symbol or Alloy signature name. */
        fun fromAtlas(operator: String): BinaryOperator = values().firstOrNull {
            it.symbol == operator || it.atlasName == operator
        } ?: throw IllegalArgumentException("Not an ATLAS binary operator: $operator")
    }
}
