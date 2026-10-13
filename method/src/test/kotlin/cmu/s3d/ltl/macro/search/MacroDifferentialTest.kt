package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.*
import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.NodeId
import cmu.s3d.ltl.macro.kernel.PortKind
import cmu.s3d.ltl.macro.kernel.UFreeLassoOracle
import cmu.s3d.ltl.macro.unary.UnaryOperator
import org.junit.jupiter.api.Test
import java.io.File
import java.util.Random
import kotlin.test.*

class MacroDifferentialTest {
    private fun trace(random: Random, aps: List<String>): LassoTrace {
        val length = 1 + random.nextInt(4)
        val loop = random.nextInt(length)
        val states = (0 until length).map { State(aps.associateWith { random.nextBoolean() }) }
        return LassoTrace(states.take(loop),states.drop(loop))
    }
    private fun <Q : Any> compare(plan: MacroConstraintPlan<Q>, pos: List<LassoTrace>, neg: List<LassoTrace>, case: String): Boolean {
        val expected = TinyReferenceEnumerator.optimum(plan,pos,neg)
        val result = MacroLearner(plan,pos,neg).solve()
        assertEquals(expected?.size,result.dag?.size(),case)
        assertEquals(expected?.kept,result.assignment?.keptEdges,case)
        result.dag?.let { dag ->
            assertTrue(pos.all { UFreeLassoOracle.evaluate(dag,it)[0] },case)
            assertTrue(neg.none { UFreeLassoOracle.evaluate(dag,it)[0] },case)
        }
        return result.dag != null
    }

    @Test fun twoHundredTinyTasksMatchIndependentDagEnumeration() {
        val random = Random(20260922)
        var sat = 0
        for (i in 0 until 200) {
            val aps = if (i % 2 == 0) listOf("p") else listOf("p","q")
            val unary = listOf(UnaryOperator.LEXICAL_ORDER[(i / 2) % 4])
            val bin = listOf(listOf(BinaryOperator.AND,BinaryOperator.OR,BinaryOperator.IMPLIES)[(i / 8) % 3])
            val bound = 1 + (i / 3) % 4
            val b = (i / 5) % 3
            val profile: ConstraintAutomaton<*> = when (i % 8) {
                0 -> PropositionalAutomaton(); 1 -> NnfAutomaton(); 2 -> CnfAutomaton(); 3 -> DnfAutomaton()
                4 -> RequiredPropositionAutomaton(aps.last()); 5 -> FixedTemplateAutomaton()
                6 -> FixedTemplateAutomaton(true); else -> ProductConstraintAutomaton(listOf(NnfAutomaton(),RequiredPropositionAutomaton(aps.last())))
            }
            val plan = MacroConstraintPlan(ProductConstraintAutomaton(if (i % 3 == 0) emptyList() else listOf(profile)), aps, bound,b,unary,bin)
            val pos = if (i % 7 == 0) emptyList() else listOf(trace(random,aps))
            val neg = if (i % 11 == 0) pos else listOf(trace(random,aps))
            if (compare(plan,pos,neg,"tiny case $i")) sat++
        }
        // Boundary B=5 and both binary counts, with sharing explicitly available.
        for (b in 0..2) {
            val plan = MacroConstraintPlan(ProductConstraintAutomaton(listOf(RequiredPropositionAutomaton("q"))), listOf("p","q"),5,b,
                listOf(UnaryOperator.NOT),listOf(BinaryOperator.AND))
            if (compare(plan,listOf(trace(random,plan.propositions)),listOf(trace(random,plan.propositions)),"B5 b$b")) sat++
        }
        // Mixed words exercise NOT duality, X shifts, FG/GF and complete product fibers in the solver.
        for (i in 0 until 40) {
            val profiles = when(i%4) {
                0 -> emptyList(); 1 -> listOf(NnfAutomaton()); 2 -> listOf(RequiredPropositionAutomaton("p"))
                else -> listOf(NnfAutomaton(),RequiredPropositionAutomaton("p"))
            }
            val plan=MacroConstraintPlan(ProductConstraintAutomaton(profiles),listOf("p"),3+i%2,1,
                UnaryOperator.LEXICAL_ORDER,listOf(BinaryOperator.IMPLIES))
            val pos=listOf(trace(random,plan.propositions),trace(random,plan.propositions))
            val neg=listOf(trace(random,plan.propositions),trace(random,plan.propositions))
            if(compare(plan,pos,neg,"mixed $i")) sat++
        }
        File("target/phase3-tiny-results.txt").writeText("seed=20260922\ntasks=243\nSAT=$sat\nUNSAT=${243-sat}\nmismatches=0\n")
    }

    @Test fun fiftyRepairTasksMatchLexicographicReference() {
        val random = Random(920226)
        val a = NodeId("A"); val u = NodeId("U"); val p = NodeId("P")
        val named = listOf(ProtectedIdentity(a,MacroLabel.Binary(BinaryOperator.AND)),
            ProtectedIdentity(u,MacroLabel.Unary(UnaryOperator.F)),ProtectedIdentity(p,MacroLabel.Literal("p")))
        val pairs = listOf(ProtectedEdge(a,u),ProtectedEdge(a,p),ProtectedEdge(u,p),ProtectedEdge(u,a),ProtectedEdge(p,a))
        var sat = 0
        for (i in 0 until 50) {
            val identities = arrayListOf<MacroIdentityConstraint>(MacroIdentityConstraint.NamedRoot(a))
            if(i%4==0) identities.add(MacroIdentityConstraint.LeftNotEqualRight)
            if(i%5==0) identities.add(MacroIdentityConstraint.NoDAGReuse(i%10==0))
            if(i%7==0) identities.add(MacroIdentityConstraint.NamedDirectChild(a,PortKind.LEFT,u))
            if(i%9==0) identities.add(MacroIdentityConstraint.NamedReachability(u,p))
            val plan = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),3+i%3,1,
                listOf(UnaryOperator.F),listOf(BinaryOperator.AND),named,identities,
                MacroObjective.Repair(pairs.filterIndexed { j,_ -> (i+1) and (1 shl j) != 0 }))
            val pos = if(i%3==0) emptyList() else listOf(trace(random,listOf("p")))
            val neg = if(i%4==0) emptyList() else listOf(trace(random,listOf("p")))
            if(compare(plan,pos,neg,"repair case $i")) sat++
        }
        File("target/phase3-repair-results.txt").writeText("seed=920226\ntasks=50\nSAT=$sat\nUNSAT=${50-sat}\nmismatches=0\nobjective=max kept distinct pairs, then min size\n")
    }
}
