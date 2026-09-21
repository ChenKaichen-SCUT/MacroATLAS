package cmu.s3d.ltl.macro.unary

/** Deterministic unary-context normalizer for infinite-trace LTL over !, X, F, G. */
object UnaryNormalizer {
    /** Read an outer-to-inner word from the inside out; no string rewriting is used. */
    fun normalize(word: UnaryWord): SemanticType = word.operators.asReversed().fold(SemanticType.IDENTITY) {
        state, operator -> prefix(operator, state)
    }

    /** Compute the semantic state of operator(context), commuting X to the outside. */
    fun prefix(operator: UnaryOperator, state: SemanticType): SemanticType = when (operator) {
        UnaryOperator.X -> state.copy(xCount = Math.addExact(state.xCount, 1))
        UnaryOperator.NOT -> state.copy(tail = state.tail.dual(), negated = !state.negated)
        UnaryOperator.F -> state.copy(tail = when (state.tail) {
            TemporalTail.ID, TemporalTail.F -> TemporalTail.F
            TemporalTail.G, TemporalTail.FG -> TemporalTail.FG
            TemporalTail.GF -> TemporalTail.GF
        })
        UnaryOperator.G -> state.copy(tail = when (state.tail) {
            TemporalTail.ID, TemporalTail.G -> TemporalTail.G
            TemporalTail.F, TemporalTail.GF -> TemporalTail.GF
            TemporalTail.FG -> TemporalTail.FG
        })
    }

    /** Materialize X...X + temporal tail + optional !; this need not preserve syntax constraints. */
    fun canonicalWord(state: SemanticType): UnaryWord {
        val operators = ArrayList<UnaryOperator>()
        repeat(state.xCount) { operators.add(UnaryOperator.X) }
        when (state.tail) {
            TemporalTail.ID -> Unit
            TemporalTail.F -> operators.add(UnaryOperator.F)
            TemporalTail.G -> operators.add(UnaryOperator.G)
            TemporalTail.FG -> operators.addAll(listOf(UnaryOperator.F, UnaryOperator.G))
            TemporalTail.GF -> operators.addAll(listOf(UnaryOperator.G, UnaryOperator.F))
        }
        if (state.negated) operators.add(UnaryOperator.NOT)
        return UnaryWord(operators)
    }

    /** Compare unary semantic contexts, without claiming syntactic interchangeability. */
    fun sameSemanticType(a: UnaryWord, b: UnaryWord): Boolean = normalize(a) == normalize(b)
}
