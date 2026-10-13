package cmu.s3d.ltl.macro

import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.unary.UnaryOperator
import org.junit.jupiter.api.Test
import kotlin.random.Random
import kotlin.test.*

class ConstraintAutomataTests {
    // Minimal test fixtures only: production continues to use ATLAS's syntax DAG.
    private sealed class Formula {
        data class Atom(val name: String) : Formula()
        data class Unary(val op: UnaryOperator, val child: Formula) : Formula()
        data class Binary(val op: BinaryOperator, val left: Formula, val right: Formula) : Formula()
    }

    private val p = Formula.Atom("p")
    private val q = Formula.Atom("q")
    private val r = Formula.Atom("r")
    private val s = Formula.Atom("s")
    private fun neg(f: Formula) = Formula.Unary(UnaryOperator.NOT, f)
    private fun g(f: Formula) = Formula.Unary(UnaryOperator.G, f)
    private fun f(f: Formula) = Formula.Unary(UnaryOperator.F, f)
    private fun and(a: Formula, b: Formula) = Formula.Binary(BinaryOperator.AND, a, b)
    private fun or(a: Formula, b: Formula) = Formula.Binary(BinaryOperator.OR, a, b)

    private fun <S : Any> run(automaton: ConstraintAutomaton<S>, formula: Formula): S = when (formula) {
        is Formula.Atom -> automaton.literalState(formula.name)
        is Formula.Unary -> automaton.unaryState(formula.op, run(automaton, formula.child))
        is Formula.Binary -> automaton.binaryState(formula.op, run(automaton, formula.left), run(automaton, formula.right))
    }

    private fun <S : Any> examples(automaton: ConstraintAutomaton<S>, valid: List<Formula>, invalid: List<Formula>) {
        for (formula in valid) assertTrue(automaton.isAccepting(run(automaton, formula)), formula.toString())
        for (formula in invalid) assertFalse(automaton.isAccepting(run(automaton, formula)), formula.toString())
    }

    @Test
    fun nnfAcceptsExactlyTheRequiredExamples() {
        examples(NnfAutomaton(), listOf(p, neg(p), g(neg(p)), f(and(p, neg(q)))),
            listOf(neg(neg(p)), neg(g(p)), neg(and(p, q))))
    }

    @Test
    fun cnfAcceptsExactlyTheRequiredExamples() {
        examples(CnfAutomaton(), listOf(p, neg(p), or(p, q), and(or(p, neg(q)), or(r, s)), and(and(p, q), r)),
            listOf(or(p, and(q, r)), neg(neg(p)), g(p), or(and(q, r), p)))
    }

    @Test
    fun dnfAcceptsExactlyTheRequiredExamples() {
        examples(DnfAutomaton(), listOf(p, neg(p), and(p, q), or(and(p, neg(q)), and(r, s))),
            listOf(and(p, or(q, r)), neg(neg(p)), g(p), and(or(q, r), p)))
    }

    @Test
    fun propositionalOnlyRejectsAllTemporalOperatorsIncludingUntil() {
        val automaton = PropositionalAutomaton()
        examples(automaton, listOf(p, neg(neg(p)), neg(and(p, or(q, r)))), listOf(g(p), f(p)))
        for (op in BinaryOperator.values()) {
            assertEquals(op != BinaryOperator.UNTIL,
                automaton.isAccepting(run(automaton, Formula.Binary(op, p, q))))
            for (a in PropositionalAutomaton.State.values()) for (b in PropositionalAutomaton.State.values()) {
                assertEquals(op != BinaryOperator.UNTIL && a == PropositionalAutomaton.State.PROP && b == a,
                    automaton.isAccepting(automaton.binaryState(op, a, b)))
            }
        }
        for (op in UnaryOperator.values()) for (state in PropositionalAutomaton.State.values()) {
            assertEquals(op == UnaryOperator.NOT && state == PropositionalAutomaton.State.PROP,
                automaton.isAccepting(automaton.unaryState(op, state)))
        }
    }

    @Test
    fun requiredPropositionUsesExactAtlasNamesAndPropagatesEveryOperator() {
        val automaton = RequiredPropositionAutomaton("x1")
        assertEquals(RequiredPropositionAutomaton.State.PRESENT, automaton.literalState("x1"))
        for (name in listOf("x0", "x10", "X1", "x1 ")) {
            assertEquals(RequiredPropositionAutomaton.State.ABSENT, automaton.literalState(name))
        }
        for (state in RequiredPropositionAutomaton.State.values()) for (op in UnaryOperator.values()) {
            assertEquals(state, automaton.unaryState(op, state))
        }
        for (a in RequiredPropositionAutomaton.State.values()) for (b in RequiredPropositionAutomaton.State.values()) {
            for (op in BinaryOperator.values()) assertEquals(
                a == RequiredPropositionAutomaton.State.PRESENT || b == RequiredPropositionAutomaton.State.PRESENT,
                automaton.isAccepting(automaton.binaryState(op, a, b))
            )
        }
    }

    @Test
    fun invalidStatesAreAbsorbingAndNnfRetainsAtlasBinarySyntax() {
        val nnf = NnfAutomaton()
        val cnf = CnfAutomaton()
        val dnf = DnfAutomaton()
        checkInvalidAbsorbing(nnf, NnfAutomaton.State.INVALID, NnfAutomaton.State.values().toList())
        checkInvalidAbsorbing(cnf, CnfAutomaton.State.INVALID, CnfAutomaton.State.values().toList())
        checkInvalidAbsorbing(dnf, DnfAutomaton.State.INVALID, DnfAutomaton.State.values().toList())
        for (op in BinaryOperator.values()) {
            assertEquals(NnfAutomaton.State.VALID_NON_ATOM,
                nnf.binaryState(op, NnfAutomaton.State.ATOM, NnfAutomaton.State.VALID_NON_ATOM))
        }
        for (op in listOf(BinaryOperator.IMPLIES, BinaryOperator.UNTIL)) {
            assertFalse(cnf.isAccepting(run(cnf, Formula.Binary(op, p, q))))
            assertFalse(dnf.isAccepting(run(dnf, Formula.Binary(op, p, q))))
        }
    }

    private fun <S : Any> checkInvalidAbsorbing(automaton: ConstraintAutomaton<S>, invalid: S, states: List<S>) {
        for (op in UnaryOperator.values()) assertEquals(invalid, automaton.unaryState(op, invalid))
        for (op in BinaryOperator.values()) for (state in states) {
            assertEquals(invalid, automaton.binaryState(op, invalid, state))
            assertEquals(invalid, automaton.binaryState(op, state, invalid))
        }
    }

    @Test
    fun productAppliesTransitionsComponentWiseAndRequiresAllComponentsToAccept() {
        val nnf = NnfAutomaton()
        val required = RequiredPropositionAutomaton("p")
        val product = ProductConstraintAutomaton(listOf(nnf, required))
        examples(product, listOf(g(neg(p))), listOf(g(neg(q)), neg(g(p))))
        val fixtures = listOf(p, q, neg(p), g(neg(p)), g(neg(q)), neg(g(p)), and(p, q), or(neg(g(p)), q))
        for (formula in fixtures) {
            val state = run(product, formula)
            assertEquals(listOf(run(nnf, formula), run(required, formula)), state.components)
            assertEquals(nnf.isAccepting(run(nnf, formula)) && required.isAccepting(run(required, formula)),
                product.isAccepting(state))
        }
    }

    @Test
    fun productStatesAreLazyInternedImmutableAndOwned() {
        val source = mutableListOf<ConstraintAutomaton<*>>(NnfAutomaton(), RequiredPropositionAutomaton("p"))
        val product = ProductConstraintAutomaton(source)
        source.clear()
        assertEquals(0, product.internedStateCount)
        val p = product.literalState("p")
        assertEquals(1, product.internedStateCount)
        assertSame(p, product.literalState("p"))
        assertEquals(1, product.internedStateCount)
        assertEquals(2, p.components.size)
        assertFailsWith<UnsupportedOperationException> { (p.components as MutableList).clear() }
        val negP = product.unaryState(UnaryOperator.NOT, p)
        assertSame(negP, product.unaryState(UnaryOperator.G, p))
        assertSame(negP, product.binaryState(BinaryOperator.AND, p, p))
        assertEquals(2, product.internedStateCount)
        assertEquals("present", hashMapOf(p to "present")[product.literalState("p")])
        val foreign = ProductConstraintAutomaton(listOf(NnfAutomaton(), RequiredPropositionAutomaton("p"))).literalState("p")
        assertNotEquals(p, foreign)
        assertFailsWith<IllegalArgumentException> { product.unaryState(UnaryOperator.F, foreign) }
        assertFailsWith<IllegalArgumentException> { product.binaryState(BinaryOperator.AND, p, foreign) }
        assertFailsWith<IllegalArgumentException> { product.binaryState(BinaryOperator.AND, foreign, p) }
        assertFailsWith<IllegalArgumentException> { product.isAccepting(foreign) }
    }

    @Test
    fun emptyAndNestedProductsHaveWellDefinedBehavior() {
        val empty = ProductConstraintAutomaton(emptyList())
        assertEquals(0, empty.internedStateCount)
        val state = empty.literalState("p")
        assertTrue(empty.isAccepting(state))
        assertSame(state, empty.unaryState(UnaryOperator.NOT, state))
        assertSame(state, empty.binaryState(BinaryOperator.UNTIL, state, state))
        assertEquals(1, empty.internedStateCount)
        val nested = ProductConstraintAutomaton(listOf(
            ProductConstraintAutomaton(listOf(NnfAutomaton(), RequiredPropositionAutomaton("p"))),
            PropositionalAutomaton(), RequiredPropositionAutomaton("q")
        ))
        examples(nested, listOf(and(p, neg(q))), listOf(and(p, p), g(and(p, q)), neg(and(p, q))))
    }

    @Test
    fun minimizedAutomatonPreservesEveryGeneratedContextAndShrinksWeakening() {
        val unary = listOf(UnaryOperator.NOT, UnaryOperator.G)
        val binary = listOf(BinaryOperator.AND, BinaryOperator.OR, BinaryOperator.IMPLIES)
        val raw = WeakeningTemplateAutomaton(false)
        val minimized = MinimizedConstraintAutomaton(raw,listOf("x0","x1","x2"),unary,binary)
        assertEquals(35,minimized.rawStateCount)
        assertEquals(15,minimized.stateCount)
        val atoms = listOf("x0","x1","x2").map { Formula.Atom(it) }
        val random = Random(923)
        fun generate(depth:Int):Formula = when(if(depth==0) 0 else random.nextInt(3)) {
            0 -> atoms.random(random)
            1 -> Formula.Unary(unary.random(random),generate(depth-1))
            else -> Formula.Binary(binary.random(random),generate(depth-1),generate(depth-1))
        }
        repeat(3000) {
            val formula=generate(5)
            assertEquals(raw.isAccepting(run(raw,formula)),minimized.isAccepting(run(minimized,formula)),formula.toString())
        }
    }

    @Test
    fun automataAgreeWithIndependentStructuralPredicatesOnGeneratedFormulas() {
        val nnf = NnfAutomaton()
        val cnf = CnfAutomaton()
        val dnf = DnfAutomaton()
        val prop = PropositionalAutomaton()
        val required = RequiredPropositionAutomaton("p")
        val product = ProductConstraintAutomaton(listOf(nnf, cnf, dnf, prop, required))
        val random = Random(741)
        fun generate(depth: Int): Formula = when (if (depth == 0) 0 else random.nextInt(3)) {
            0 -> if (random.nextBoolean()) p else q
            1 -> Formula.Unary(UnaryOperator.values()[random.nextInt(4)], generate(depth - 1))
            else -> Formula.Binary(BinaryOperator.values()[random.nextInt(4)], generate(depth - 1), generate(depth - 1))
        }
        repeat(3000) {
            val formula = generate(5)
            val nodes = descendants(formula)
            val nnfExpected = nodes.none { it is Formula.Unary && it.op == UnaryOperator.NOT && it.child !is Formula.Atom }
            val propExpected = nodes.none {
                (it is Formula.Unary && it.op != UnaryOperator.NOT) || (it is Formula.Binary && it.op == BinaryOperator.UNTIL)
            }
            val booleanGrammar = nnfExpected && nodes.all {
                it is Formula.Atom || (it is Formula.Unary && it.op == UnaryOperator.NOT) ||
                    (it is Formula.Binary && it.op in listOf(BinaryOperator.AND, BinaryOperator.OR))
            }
            val cnfExpected = booleanGrammar && nodes.none {
                it is Formula.Binary && it.op == BinaryOperator.OR && descendants(it).any { n -> n is Formula.Binary && n.op == BinaryOperator.AND }
            }
            val dnfExpected = booleanGrammar && nodes.none {
                it is Formula.Binary && it.op == BinaryOperator.AND && descendants(it).any { n -> n is Formula.Binary && n.op == BinaryOperator.OR }
            }
            val requiredExpected = p in nodes
            assertEquals(nnfExpected, nnf.isAccepting(run(nnf, formula)), formula.toString())
            assertEquals(cnfExpected, cnf.isAccepting(run(cnf, formula)), formula.toString())
            assertEquals(dnfExpected, dnf.isAccepting(run(dnf, formula)), formula.toString())
            assertEquals(propExpected, prop.isAccepting(run(prop, formula)), formula.toString())
            assertEquals(requiredExpected, required.isAccepting(run(required, formula)), formula.toString())
            assertEquals(nnfExpected && cnfExpected && dnfExpected && propExpected && requiredExpected,
                product.isAccepting(run(product, formula)), formula.toString())
        }
    }

    private fun descendants(formula: Formula): List<Formula> = listOf(formula) + when (formula) {
        is Formula.Atom -> emptyList()
        is Formula.Unary -> descendants(formula.child)
        is Formula.Binary -> descendants(formula.left) + descendants(formula.right)
    }
}
