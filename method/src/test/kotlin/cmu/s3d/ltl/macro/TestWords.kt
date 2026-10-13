package cmu.s3d.ltl.macro

import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.macro.unary.UnaryWord

/** Test-only convenience for compact words, not a formula parser. */
internal fun word(symbols: String): UnaryWord = UnaryWord(symbols.map { UnaryOperator.fromAtlas(it.toString()) })

/** Exhaustive syntax enumeration, independent of semantic states and BFS pruning. */
internal fun allWords(
    maxLength: Int,
    alphabet: List<UnaryOperator> = UnaryOperator.LEXICAL_ORDER
): Sequence<UnaryWord> = sequence {
    suspend fun SequenceScope<UnaryWord>.visit(prefix: List<UnaryOperator>) {
        yield(UnaryWord(prefix))
        if (prefix.size < maxLength) for (operator in alphabet) visit(prefix + operator)
    }
    visit(emptyList())
}

/** Independent shortlex oracle: explicit symbol ranks, not UnaryWord.compareTo. */
internal fun isBetter(candidate: UnaryWord, previous: UnaryWord): Boolean {
    if (candidate.length != previous.length) return candidate.length < previous.length
    val symbols = listOf("!", "X", "F", "G")
    for ((a, b) in candidate.operators.zip(previous.operators)) {
        if (a != b) return symbols.indexOf(a.symbol) < symbols.indexOf(b.symbol)
    }
    return false
}
