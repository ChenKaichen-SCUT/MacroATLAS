package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.*
import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.*
import cmu.s3d.ltl.macro.kernel.*
import org.junit.jupiter.api.Test
import kotlin.test.*

class MacroSearchTest {
    private fun trace(vararg values: Boolean) = LassoTrace(loop = values.map { State(mapOf("p" to it)) })
    @Test fun certifiedSmallFormulaBoundPreservesTheOptimalDagAndRejectsLargerOptima() {
        val plain = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),4,1,
            listOf(UnaryOperator.NOT),listOf(BinaryOperator.AND))
        val literal = MacroLearner(plain,listOf(trace(true)),listOf(trace(false))).solve()
        assertEquals(1,literal.dag!!.size())
        assertEquals(1,literal.metadata["smallFormulaBound"])
        assertEquals(1,literal.assignment!!.expandedSize)

        val negated = MacroLearner(plain,listOf(trace(false)),listOf(trace(true))).solve()
        assertEquals(2,negated.dag!!.size())
        assertEquals(2,negated.metadata["smallFormulaBound"])
        assertEquals(2,negated.assignment!!.expandedSize)

        val andRoot = MacroConstraintPlan(RootOperatorAutomaton("And"),listOf("p"),3,1,
            emptyList(),listOf(BinaryOperator.AND))
        val shared = MacroLearner(andRoot,listOf(trace(true)),listOf(trace(false))).solve()
        assertEquals(2,shared.dag!!.size())
        assertEquals(2,shared.metadata["smallFormulaBound"])

        fun pq(p:Boolean,q:Boolean) = LassoTrace(loop=listOf(State(mapOf("p" to p,"q" to q))))
        val conjunction = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p","q"),3,1,
            emptyList(),listOf(BinaryOperator.AND))
        val larger = MacroLearner(conjunction,listOf(pq(true,true)),listOf(pq(false,true),pq(true,false))).solve()
        assertEquals(3,larger.dag!!.size())
        assertEquals(0,larger.metadata["smallFormulaBound"])
    }

    @Test fun requiredGlobalRootHasAnEquivalentAnchoredRepresentation() {
        fun plan(fixed: Boolean) = MacroConstraintPlan(RootOperatorAutomaton("G"),listOf("p"),4,0,
            listOf(UnaryOperator.F,UnaryOperator.G),emptyList(),
            requiredRootUnary = if (fixed) UnaryOperator.G else null)
        for ((positives,negatives,size) in listOf(
            Triple(listOf(trace(true)),listOf(trace(false)),2),
            Triple(listOf(trace(false,true)),listOf(trace(false,false)),3)
        )) {
            val original = MacroLearner(plan(false),positives,negatives).solve()
            val anchored = MacroLearner(plan(true),positives,negatives).solve()
            assertEquals(size,original.dag!!.size())
            assertEquals(size,anchored.dag!!.size())
            assertIs<UnaryNode>(anchored.dag!!.node(anchored.dag!!.root))
        }
    }

    @Test fun directSearchLearnsLiteralAndNegationAndReportsUnsat() {
        for (neg in listOf(false, true)) {
            val plan = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()), listOf("p"), 2, 0,
                listOf(UnaryOperator.NOT), emptyList())
            val result = MacroLearner(plan, listOf(trace(!neg)), listOf(trace(neg))).solve()
            assertEquals(if (neg) 2 else 1, result.dag!!.size())
        }
        val plan = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()), listOf("p"), 1, 0)
        assertNull(MacroLearner(plan, listOf(trace(true)), listOf(trace(true))).solve().dag)
    }

    @Test fun expandedNodeBoundAndBinaryBoundAreHard() {
        val trueTrace = trace(true)
        for (bound in 1..3) {
            val plan = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),bound,0,listOf(UnaryOperator.NOT),emptyList())
            assertEquals(if(bound<2) null else 2,MacroLearner(plan,listOf(trace(false)),listOf(trueTrace)).solve().dag?.size())
        }
        val count = object : ConstraintAutomaton<Int> {
            override fun literalState(proposition: String) = 0
            override fun unaryState(operator: UnaryOperator, child: Int) = child
            override fun binaryState(operator: BinaryOperator, left: Int, right: Int) = minOf(2,1+maxOf(left,right))
            override fun isAccepting(state: Int) = state == 2
        }
        for(b in 0..2) {
            val plan = MacroConstraintPlan(count,listOf("p"),3,b,emptyList(),listOf(BinaryOperator.AND))
            assertEquals(if(b<2) null else 3,MacroLearner(plan,listOf(trueTrace),emptyList()).solve().dag?.size())
        }
    }

    @Test fun distinctParentsAreDifferentFromIncomingPortsAndFreshHeads() {
        val a=NodeId("A"); val p=NodeId("P")
        val named=listOf(ProtectedIdentity(a,MacroLabel.Binary(BinaryOperator.AND)),ProtectedIdentity(p,MacroLabel.Literal("p")))
        fun plan(bound:Int, different:Boolean, noReuse:Boolean) = MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),bound,1,
            listOf(UnaryOperator.F),listOf(BinaryOperator.AND),named,
            listOf(MacroIdentityConstraint.NamedRoot(a)) + (if(different) listOf(MacroIdentityConstraint.LeftNotEqualRight) else emptyList()) +
                (if(noReuse) listOf(MacroIdentityConstraint.NoDAGReuse()) else emptyList()),
            MacroObjective.Repair(listOf(ProtectedEdge(a,p))),uniqueLiteralIdentities=true)
        val direct=MacroLearner(plan(2,false,true),listOf(trace(true)),emptyList()).solve()
        assertEquals(2,direct.dag!!.size())
        assertEquals(1,direct.assignment!!.keptEdges) // LEFT and RIGHT are one old pair.
        assertEquals(1,direct.dag!!.parents(p).size)
        assertNull(MacroLearner(plan(2,true,false),listOf(trace(true)),emptyList()).solve().dag)
        val wrapped=MacroLearner(plan(3,true,false),listOf(trace(true)),emptyList()).solve()
        assertEquals(3,wrapped.dag!!.size())
        assertNull(MacroLearner(plan(3,true,true),listOf(trace(true)),emptyList()).solve().dag)
    }

    @Test fun protectedOrderIsIndependentOfTopologicalOrderAndImpossibleProtectionIsUnsat() {
        val leaf=NodeId("A_leaf"); val root=NodeId("Z_root")
        val named=listOf(ProtectedIdentity(leaf,MacroLabel.Literal("p")),ProtectedIdentity(root,MacroLabel.Unary(UnaryOperator.F)))
        for (bound in 1..2) {
            val plan=MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),bound,0,
                listOf(UnaryOperator.F),emptyList(),named,listOf(MacroIdentityConstraint.NamedRoot(root),MacroIdentityConstraint.NamedDirectChild(root,PortKind.CHILD,leaf)))
            val result=MacroLearner(plan,listOf(trace(true)),emptyList()).solve()
            assertEquals(if(bound==1) null else root,result.dag?.root)
        }
    }

    @Test fun corruptAssignmentFailsVerificationInsteadOfYieldingAFormula() {
        val plan=MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),2,0,listOf(UnaryOperator.NOT),emptyList())
        val context=MacroCompilationContext(plan,listOf(trace(false)),listOf(trace(true)))
        val original=MacroLearner(context).solve().assignment!!
        val bad=original.copy(expandedSize=original.expandedSize+1)
        assertFailsWith<IllegalStateException> { FinalSolutionVerifier.verify(context,bad,MacroAssignmentDecoder.decode(context,bad)) }
        val empty=context.catalog.entries.single { !it.key.nonEmpty }
        val badFiber=original.copy(ports=original.ports + ("R" to original.ports.getValue("R").copy(fiber=empty.id)))
        var fallbacks=0
        assertFails {
            MacroTaskDispatcher.run(MacroSolverMode.AUTO,{MacroTaskAnalysis.Supported(plan,emptyList())},
                { fallbacks++; original.expandedSize },
                { FinalSolutionVerifier.verify(context,badFiber,MacroAssignmentDecoder.decode(context,badFiber)).size() })
        }
        assertEquals(0,fallbacks)
    }

    @Test fun sharedUnaryAnchorAndResponseTemplateAreFoundDirectly() {
        val plan=MacroConstraintPlan(RootOperatorAutomaton("And"),listOf("p"),3,1,
            listOf(UnaryOperator.F),listOf(BinaryOperator.AND))
        val result=MacroLearner(plan,listOf(trace(false,true)),listOf(trace(false))).solve()
        val dag=result.dag!!
        assertEquals(3,dag.size())
        val shared=dag.nodes.values.filterIsInstance<UnaryNode>().single()
        assertEquals(2,dag.indegree(shared.id))
        assertEquals(1,dag.parents(shared.id).size)
        val response=MacroConstraintPlan(FixedTemplateAutomaton(true),listOf("p"),4,1,
            listOf(UnaryOperator.F,UnaryOperator.G),listOf(BinaryOperator.IMPLIES))
        assertEquals(4,MacroLearner(response,listOf(trace(true)),emptyList()).solve().dag!!.size())
    }

    @Test fun twoNonemptyFibersHaveDistinctPrivateHeadsDespiteIdenticalTargets() {
        val a=NodeId("A"); val p=NodeId("P")
        val plan=MacroConstraintPlan(ProductConstraintAutomaton(emptyList()),listOf("p"),4,1,
            listOf(UnaryOperator.F),listOf(BinaryOperator.AND),
            listOf(ProtectedIdentity(a,MacroLabel.Binary(BinaryOperator.AND)),ProtectedIdentity(p,MacroLabel.Literal("p"))),
            listOf(MacroIdentityConstraint.LeftNotEqualRight))
        val context=MacroCompilationContext(plan,emptyList(),emptyList())
        val empty=context.catalog.entries.single { !it.key.nonEmpty }.id
        val f=context.catalog.entries.single { it.word == UnaryWord(UnaryOperator.F) }.id
        val assignment=MacroAssignment(mapOf(0 to AnchorAssignment(plan.labels.indexOf(MacroLabel.Binary(BinaryOperator.AND)),0),
            1 to AnchorAssignment(plan.labels.indexOf(MacroLabel.Literal("p")),0)),
            mapOf("R" to PortAssignment(0,empty),"L0" to PortAssignment(1,f),"D0" to PortAssignment(1,f)),4,0,emptySet(),emptySet())
        val dag=FinalSolutionVerifier.verify(context,assignment,MacroAssignmentDecoder.decode(context,assignment))
        val root=dag.node(a) as BinaryNode
        assertNotEquals(root.left,root.right)
        assertEquals(2,dag.parents(p).size)
    }
}
