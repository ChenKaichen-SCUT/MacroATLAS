package cmu.s3d.ltl.macro

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.State
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.unary.SemanticType
import cmu.s3d.ltl.macro.unary.TemporalTail
import cmu.s3d.ltl.macro.unary.UnaryNormalizer
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.macro.unary.UnaryWord
import org.junit.jupiter.api.Test
import kotlin.random.Random
import kotlin.test.*

class UnaryNormalizerTests {
    @Test
    fun knownIdentitiesAndDualityArePreserved() {
        for ((a, b) in listOf(
            "FF" to "F", "GG" to "G", "FGF" to "GF", "GFG" to "FG",
            "FX" to "XF", "GX" to "XG", "!X" to "X!", "!F" to "G!",
            "!G" to "F!", "!!" to "", "!FG" to "GF!", "!GF" to "FG!"
        )) assertTrue(UnaryNormalizer.sameSemanticType(word(a), word(b)), "$a == $b")
        assertFalse(UnaryNormalizer.sameSemanticType(word("FG"), word("GF")))
        assertFalse(UnaryNormalizer.sameSemanticType(word("!"), word("")))
        assertFalse(UnaryNormalizer.sameSemanticType(word("X"), word("")))
    }

    @Test
    fun prefixMatchesEveryFrozenTransition() {
        val tails = TemporalTail.values().toList()
        val prefixF = listOf(TemporalTail.F, TemporalTail.F, TemporalTail.FG, TemporalTail.FG, TemporalTail.GF)
        val prefixG = listOf(TemporalTail.G, TemporalTail.GF, TemporalTail.G, TemporalTail.FG, TemporalTail.GF)
        val dual = listOf(TemporalTail.ID, TemporalTail.G, TemporalTail.F, TemporalTail.GF, TemporalTail.FG)
        for (k in 0..3) for (negated in listOf(false, true)) for ((i, tail) in tails.withIndex()) {
            val state = SemanticType(k, tail, negated)
            assertEquals(SemanticType(k + 1, tail, negated), UnaryNormalizer.prefix(UnaryOperator.X, state))
            assertEquals(SemanticType(k, prefixF[i], negated), UnaryNormalizer.prefix(UnaryOperator.F, state))
            assertEquals(SemanticType(k, prefixG[i], negated), UnaryNormalizer.prefix(UnaryOperator.G, state))
            assertEquals(SemanticType(k, dual[i], !negated), UnaryNormalizer.prefix(UnaryOperator.NOT, state))
        }
    }

    @Test
    fun normalizationIsIdempotentAndCanonicalLengthNeverIncreasesThroughLength8() {
        var count = 0
        for (word in allWords(8)) {
            val type = UnaryNormalizer.normalize(word)
            val canonical = UnaryNormalizer.canonicalWord(type)
            assertEquals(type, UnaryNormalizer.normalize(canonical), "replay of $word")
            assertEquals(canonical, UnaryNormalizer.canonicalWord(UnaryNormalizer.normalize(canonical)))
            assertTrue(canonical.length <= word.length, "canonical length of $word")
            assertEquals(word.operators.count { it == UnaryOperator.X }, type.xCount)
            count++
        }
        assertEquals(87381, count)
    }

    @Test
    fun canonicalWordReplaysEveryTypeAndUsesOuterToInnerOrder() {
        for (k in 0..16) for (tail in TemporalTail.values()) for (negated in listOf(false, true)) {
            val type = SemanticType(k, tail, negated)
            assertEquals(type, UnaryNormalizer.normalize(UnaryNormalizer.canonicalWord(type)))
        }
        assertEquals(word("XXFG!"), UnaryNormalizer.canonicalWord(SemanticType(2, TemporalTail.FG, true)))
        assertEquals(SemanticType(1, TemporalTail.FG), UnaryNormalizer.normalize(word("FXG")))
        assertEquals(SemanticType(0, TemporalTail.G, true), UnaryNormalizer.normalize(word("!F")))
    }

    @Test
    fun wordsAreImmutableValueKeysAndOrderIsExplicit() {
        val source = mutableListOf(UnaryOperator.F)
        val w = UnaryWord(source)
        val lookup = hashMapOf(w to "original")
        source.clear()
        assertEquals("original", lookup[word("F")])
        assertFailsWith<UnsupportedOperationException> { (w.operators as MutableList).clear() }
        assertFailsWith<UnsupportedOperationException> { (UnaryOperator.LEXICAL_ORDER as MutableList).clear() }
        assertEquals(word("GF"), w.prepend(UnaryOperator.G))
        assertEquals("!XFG", UnaryWord(UnaryOperator.LEXICAL_ORDER).toString())
        assertEquals(listOf("", "!", "!G", "X", "F", "G"),
            listOf("G", "!G", "F", "!", "X", "").map(::word).sorted().map { it.toString() })
        assertEquals(word("XX"), word("XX"))
        assertEquals(word("XX").hashCode(), word("XX").hashCode())
    }

    @Test
    fun atlasOperatorAdaptersRespectArityAndRejectUntilInUnaryWords() {
        for (operator in UnaryOperator.values()) {
            assertEquals(operator, UnaryOperator.fromAtlas(operator.symbol))
            assertEquals(operator, UnaryOperator.fromAtlas(operator.atlasName))
        }
        for (operator in BinaryOperator.values()) {
            assertEquals(operator, BinaryOperator.fromAtlas(operator.symbol))
            assertEquals(operator, BinaryOperator.fromAtlas(operator.atlasName))
            assertFailsWith<IllegalArgumentException> { UnaryOperator.fromAtlas(operator.symbol) }
            assertFailsWith<IllegalArgumentException> { UnaryOperator.fromAtlas(operator.atlasName) }
        }
        assertFailsWith<IllegalArgumentException> { UnaryOperator.fromAtlas("unknown") }
        assertFailsWith<IllegalArgumentException> { BinaryOperator.fromAtlas("X") }
        assertFailsWith<IllegalArgumentException> { SemanticType(-1) }
        assertFailsWith<ArithmeticException> { UnaryNormalizer.prefix(UnaryOperator.X, SemanticType(Int.MAX_VALUE)) }
    }

    @Test
    fun normalizationPreservesTruthOnExhaustiveSmallLassos() {
        val words = allWords(4).toList()
        for (length in 1..4) for (loopStart in 0 until length) for (mask in 0 until (1 shl length)) {
            val states = (0 until length).map { State(mapOf("p" to (mask and (1 shl it) != 0))) }
            val trace = LassoTrace(states.take(loopStart), states.drop(loopStart))
            for (w in words) assertContentEquals(
                evaluate(w, trace), evaluate(UnaryNormalizer.canonicalWord(UnaryNormalizer.normalize(w)), trace),
                "word=$w, loopStart=$loopStart, mask=$mask"
            )
        }
    }

    @Test
    fun normalizationPreservesTruthOnSeededRandomLassosAndLongWords() {
        val random = Random(20250921)
        repeat(1000) {
            val states = List(random.nextInt(1, 21)) { State(mapOf("p" to random.nextBoolean())) }
            val loopStart = random.nextInt(states.size)
            val trace = LassoTrace(states.take(loopStart), states.drop(loopStart))
            val w = UnaryWord(List(random.nextInt(0, 65)) { UnaryOperator.values()[random.nextInt(4)] })
            assertContentEquals(evaluate(w, trace), evaluate(UnaryNormalizer.canonicalWord(UnaryNormalizer.normalize(w)), trace))
        }
    }

    // Test-only oracle over ATLAS's LassoTrace/State. F/G inspect every reachable
    // position on the actual infinite lasso (not a finite horizon or rewrite rules).
    private fun evaluate(word: UnaryWord, trace: LassoTrace): BooleanArray {
        val size = trace.length()
        fun next(i: Int): Int = if (i + 1 == size) trace.prefix.size else i + 1
        var values = BooleanArray(size) { trace.getStateAt(it).values.getValue("p") }
        for (operator in word.operators.asReversed()) {
            val child = values
            values = BooleanArray(size) { start ->
                when (operator) {
                    UnaryOperator.NOT -> !child[start]
                    UnaryOperator.X -> child[next(start)]
                    UnaryOperator.F, UnaryOperator.G -> {
                        val visited = BooleanArray(size)
                        var i = start
                        var result = operator == UnaryOperator.G
                        while (!visited[i]) {
                            visited[i] = true
                            result = if (operator == UnaryOperator.G) result && child[i] else result || child[i]
                            i = next(i)
                        }
                        result
                    }
                }
            }
        }
        return values
    }
}
