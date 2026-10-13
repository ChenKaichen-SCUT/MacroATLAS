package cmu.s3d.ltl.macro

import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.fiber.FiberKey
import cmu.s3d.ltl.macro.fiber.FiberRepresentative
import cmu.s3d.ltl.macro.fiber.FiberTable
import cmu.s3d.ltl.macro.unary.SemanticType
import cmu.s3d.ltl.macro.unary.UnaryNormalizer
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.macro.unary.UnaryWord
import org.junit.jupiter.api.Test
import kotlin.test.*

class FiberTableTests {
    @Test
    fun fiberBfsMatchesBruteForceUpToLength7ForEveryBaseAutomatonState() {
        checkEveryBound(PropositionalAutomaton(), PropositionalAutomaton.State.values().toList())
        checkEveryBound(NnfAutomaton(), NnfAutomaton.State.values().toList())
        checkEveryBound(CnfAutomaton(), CnfAutomaton.State.values().toList())
        checkEveryBound(DnfAutomaton(), DnfAutomaton.State.values().toList())
        checkEveryBound(RequiredPropositionAutomaton("p"), RequiredPropositionAutomaton.State.values().toList())
    }

    @Test
    fun fiberBfsMatchesBruteForceUpToLength7ForAllReachableProductStates() {
        val product = ProductConstraintAutomaton(listOf(
            NnfAutomaton(), CnfAutomaton(), DnfAutomaton(), PropositionalAutomaton(), RequiredPropositionAutomaton("p")
        ))
        val states = reachableStates(product)
        assertTrue(states.any { product.isAccepting(it) })
        assertTrue(states.any { !product.isAccepting(it) })
        assertEquals(states.size, product.internedStateCount)
        checkEveryBound(product, states)
    }

    @Test
    fun fiberBfsMatchesBruteForceForAnAutomatonWithRecoverableRejection() {
        // Acceptance need not be absorbing in the generic interface. In particular,
        // rejecting an intermediate state cannot justify pruning its extensions.
        val automaton = object : ConstraintAutomaton<Int> {
            override fun literalState(proposition: String) = 0
            override fun unaryState(operator: UnaryOperator, child: Int): Int = when (operator) {
                UnaryOperator.NOT -> (child + 1) % 3
                UnaryOperator.X -> (child + 2) % 3
                UnaryOperator.F -> (2 * child + 1) % 3
                UnaryOperator.G -> 0
            }
            override fun binaryState(operator: BinaryOperator, left: Int, right: Int) = (left + right) % 3
            override fun isAccepting(state: Int) = state == 0
        }
        checkEveryBound(automaton, listOf(0, 1, 2))
        val table = FiberTable(automaton, listOf(0), 3)
        assertFalse(automaton.isAccepting(table.replay(0, word("!")).qOut))
        assertTrue(automaton.isAccepting(table.replay(0, word("!!!")).qOut))
        assertNotNull(table[table.replay(0, word("!!!"))])
    }

    private fun <Q : Any> checkEveryBound(automaton: ConstraintAutomaton<Q>, states: Collection<Q>) {
        for (bound in 0..7) {
            val words = allWords(bound).toList()
            assertEquals((0..bound).sumOf { length -> 1 shl (2 * length) }, words.size)
            if (bound == 7) assertEquals(21845, words.size)
            val expected = bruteForce(automaton, states, words)
            val table = FiberTable(automaton, states, bound)
            assertEquals(expected, table.entries.mapValues { it.value.word }, "bound=$bound, automaton=$automaton")
            assertEquals(expected.keys, table.keys())
            assertEquals(expected.size, table.size())
            checkReplay(automaton, table)
        }
    }

    private fun <Q : Any> bruteForce(
        automaton: ConstraintAutomaton<Q>, states: Collection<Q>, words: List<UnaryWord>
    ): Map<FiberKey<Q>, UnaryWord> {
        val expected = HashMap<FiberKey<Q>, UnaryWord>()
        for (qIn in states) for (w in words) {
            val key = independentReplay(automaton, qIn, w)
            val previous = expected[key]
            if (previous == null || isBetter(w, previous)) expected[key] = w
        }
        return expected
    }

    private fun <Q : Any> independentReplay(automaton: ConstraintAutomaton<Q>, qIn: Q, word: UnaryWord): FiberKey<Q> {
        var qOut = qIn
        for (index in word.length - 1 downTo 0) qOut = automaton.unaryState(word.operators[index], qOut)
        return FiberKey(qIn, UnaryNormalizer.normalize(word), word.length != 0, qOut)
    }

    private fun <Q : Any> checkReplay(automaton: ConstraintAutomaton<Q>, table: FiberTable<Q>) {
        for ((key, rep) in table.entries) {
            assertTrue(rep.length <= table.maxUnaryLength)
            assertEquals(rep.word.length, rep.length)
            assertEquals(key.semanticType, UnaryNormalizer.normalize(rep.word))
            assertEquals(!key.nonEmpty, rep.word.isEmpty())
            assertTrue(rep.word.all { it in table.allowedOperators })
            assertEquals(key, independentReplay(automaton, key.qIn, rep.word))
            assertEquals(key, table.replay(key.qIn, rep.word))
            assertEquals(rep, table[key])
        }
    }

    // Reachable-state closure in a test fixture. Production product construction
    // itself remains lazy, and FiberTable never enumerates a Cartesian product.
    private fun reachableStates(product: ProductConstraintAutomaton): List<ProductState> {
        val reached = linkedSetOf(product.literalState("p"), product.literalState("q"))
        do {
            val oldSize = reached.size
            val snapshot = reached.toList()
            for (state in snapshot) for (op in UnaryOperator.values()) reached.add(product.unaryState(op, state))
            for (a in snapshot) for (b in snapshot) for (op in BinaryOperator.values()) reached.add(product.binaryState(op, a, b))
        } while (oldSize != reached.size)
        return reached.toList()
    }

    @Test
    fun fiberReplayUsesTheActualNestingDirection() {
        val nnf = NnfAutomaton()
        val atom = NnfAutomaton.State.ATOM
        val table = FiberTable(nnf, listOf(atom), 4)
        assertEquals(NnfAutomaton.State.VALID_NON_ATOM, table.replay(atom, word("F!")).qOut)
        assertEquals(NnfAutomaton.State.INVALID, table.replay(atom, word("!F")).qOut)
        assertEquals(nnf.unaryState(UnaryOperator.F, nnf.unaryState(UnaryOperator.X, nnf.unaryState(UnaryOperator.G, atom))),
            table.replay(atom, word("FXG")).qOut)
    }

    @Test
    fun nnfDistinguishesEquivalentSyntaxAndKeepsBothFibers() {
        val atom = NnfAutomaton.State.ATOM
        val table = FiberTable(NnfAutomaton(), listOf(atom), 2)
        val invalid = table.replay(atom, word("!G"))
        val valid = table.replay(atom, word("F!"))
        assertEquals(invalid.semanticType, valid.semanticType)
        assertEquals(NnfAutomaton.State.INVALID, invalid.qOut)
        assertEquals(NnfAutomaton.State.VALID_NON_ATOM, valid.qOut)
        assertNotEquals(invalid, valid)
        assertEquals(word("!G"), assertNotNull(table[invalid]).word)
        assertEquals(word("F!"), assertNotNull(table[valid]).word)
        // Substituting the plain semantic canonical word would break this fiber.
        val canonical = UnaryNormalizer.canonicalWord(invalid.semanticType)
        assertEquals(word("F!"), canonical)
        assertNotEquals(invalid, table.replay(atom, canonical))
    }

    @Test
    fun nonemptyIdentityAndInputStatesRemainDistinct() {
        val prop = PropositionalAutomaton.State.PROP
        val nonProp = PropositionalAutomaton.State.NON_PROP
        val table = FiberTable(PropositionalAutomaton(), listOf(prop, nonProp), 2)
        val empty = table.replay(prop, UnaryWord.EMPTY)
        val doubleNeg = table.replay(prop, word("!!"))
        assertEquals(empty.semanticType, doubleNeg.semanticType)
        assertEquals(empty.qOut, doubleNeg.qOut)
        assertNotEquals(empty, doubleNeg)
        assertFalse(empty.nonEmpty)
        assertTrue(doubleNeg.nonEmpty)
        assertEquals(word(""), assertNotNull(table[empty]).word)
        assertEquals(word("!!"), assertNotNull(table[doubleNeg]).word)
        assertNotEquals(table.replay(prop, word("F")), table.replay(nonProp, word("F")))
    }

    @Test
    fun lexicalTiesAreResolvedAfterEachWholeLayerAndIgnoreAlphabetInputOrder() {
        val automaton = PropositionalAutomaton()
        val states = PropositionalAutomaton.State.values().toList()
        val table = FiberTable(automaton, states, 7)
        val reversed = FiberTable(automaton, states.asReversed() + states, 7,
            UnaryOperator.LEXICAL_ORDER.asReversed() + UnaryOperator.NOT)
        assertEquals(table.entries, reversed.entries)
        assertEquals(UnaryOperator.LEXICAL_ORDER, reversed.allowedOperators)
        // With child-first FIFO discovery, FX can be encountered before XF even
        // though X < F. The complete layer must replace that first witness.
        assertEquals(word("XF"), assertNotNull(table[table.replay(states.first(), word("FX"))]).word)
    }

    @Test
    fun everyAllowedAlphabetSubsetMatchesBruteForce() {
        val automaton = NnfAutomaton()
        val states = NnfAutomaton.State.values().toList()
        for (mask in 0 until 16) {
            val alphabet = UnaryOperator.LEXICAL_ORDER.filterIndexed { index, _ -> mask and (1 shl index) != 0 }
            val table = FiberTable(automaton, states, 5, alphabet.asReversed())
            assertEquals(bruteForce(automaton, states, allWords(5, alphabet).toList()), table.entries.mapValues { it.value.word })
            checkReplay(automaton, table)
        }
    }

    @Test
    fun boundsEmptyDomainsAndMissingLookupsAreExplicit() {
        val automaton = NnfAutomaton()
        val atom = NnfAutomaton.State.ATOM
        assertFailsWith<IllegalArgumentException> { FiberTable(automaton, listOf(atom), -1) }
        val zero = FiberTable(automaton, listOf(atom), 0)
        assertEquals(1, zero.size())
        assertEquals(FiberRepresentative(word("")), zero[zero.replay(atom, word(""))])
        assertNull(zero[zero.replay(atom, word("X"))])
        assertNull(zero[zero.replay(NnfAutomaton.State.INVALID, word(""))])
        assertEquals(0, FiberTable(automaton, emptyList(), 7).size())
        val noOperators = FiberTable(automaton, NnfAutomaton.State.values().toList(), 7, emptyList())
        assertEquals(3, noOperators.size())
        assertTrue(noOperators.entries.values.all { it.word.isEmpty() })
        val emptyProduct = ProductConstraintAutomaton(emptyList())
        checkEveryBound(emptyProduct, listOf(emptyProduct.literalState("p")))
    }

    @Test
    fun fibersAndTableViewsAreImmutableValueKeys() {
        val atom = NnfAutomaton.State.ATOM
        val sourceStates = mutableListOf(atom)
        val sourceOps = mutableListOf(UnaryOperator.NOT)
        val table = FiberTable(NnfAutomaton(), sourceStates, 3, sourceOps)
        sourceStates.clear()
        sourceOps.clear()
        assertEquals(setOf(atom), table.inputStates)
        assertEquals(listOf(UnaryOperator.NOT), table.allowedOperators)
        assertFailsWith<UnsupportedOperationException> { (table.entries as MutableMap).clear() }
        assertFailsWith<UnsupportedOperationException> { (table.keys() as MutableSet).clear() }
        assertFailsWith<UnsupportedOperationException> { (table.inputStates as MutableSet).clear() }
        assertFailsWith<UnsupportedOperationException> { (table.allowedOperators as MutableList).clear() }
        val key = table.replay(atom, word(""))
        val equalKey = FiberKey(atom, SemanticType.IDENTITY, false, atom)
        assertEquals(key, equalKey)
        assertEquals(key.hashCode(), equalKey.hashCode())
        assertEquals(FiberRepresentative(word("")), table[equalKey])
    }
}
