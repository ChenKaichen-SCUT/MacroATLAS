package cmu.s3d.ltl.macro.unary

/** Immutable semantic context X^xCount tail !^negated, with negation innermost. */
data class SemanticType(
    val xCount: Int = 0,
    val tail: TemporalTail = TemporalTail.ID,
    val negated: Boolean = false
) {
    init {
        require(xCount >= 0) { "xCount must be nonnegative" }
    }

    companion object {
        /** The semantic identity; it does not record whether the syntax was empty. */
        val IDENTITY = SemanticType()
    }
}
