package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.samples2ltl.TaskParser
import cmu.s3d.ltl.macro.analysis.DagConstraintEvaluator
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator
import org.junit.jupiter.api.Test
import java.io.File
import kotlin.test.*

/** Boundary examples from actual paper inputs, with the same U-removal as E4. */
class ConstraintSemanticAuditTest {
    private fun plan(name: String, b: Int): MacroConstraintPlan<*> {
        val parts=File("benchmark/$name").readText().split("---").toMutableList()
        parts[2]=parts[2].split(',').map { it.trim() }.filter { it!="U" }.joinToString(",")
        val task=TaskParser.parseTask(parts.joinToString("---"))
        return (RecognizedConstraintAnalyzer.analyze(task,b) as MacroTaskAnalysis.Supported).plan
    }

    private fun accepts(plan: MacroConstraintPlan<*>, dag: FormulaDag): Boolean {
        fun <Q:Any> check(p: MacroConstraintPlan<Q>) =
            p.automaton.isAccepting(DagConstraintEvaluator(p.automaton).evaluate(dag).rootState)
        return check(plan)
    }

    @Test fun officialVotingAllowsTemporalDescendantsAndNnfOnlyWhereWritten() {
        val plain=plan("voting_machine/voting2.trace",2)
        val nnf=plan("voting_machine/voting10.trace",2)
        val x=NodeId("x0");val f=NodeId("f");val g=NodeId("g");val neg=NodeId("n")
        val temporal=FormulaDag(g,listOf(LiteralNode(x,"x0"),UnaryNode(f,UnaryOperator.F,x),
            UnaryNode(g,UnaryOperator.G,f)))
        assertTrue(accepts(plain,temporal))
        assertTrue(accepts(nnf,temporal))
        val nonNnf=FormulaDag(g,listOf(LiteralNode(x,"x0"),UnaryNode(f,UnaryOperator.F,x),
            UnaryNode(neg,UnaryOperator.NOT,f),UnaryNode(g,UnaryOperator.G,neg)))
        assertTrue(accepts(plain,nonNnf))
        assertFalse(accepts(nnf,nonNnf))
    }

    @Test fun weakeningQuantifiersCoverAllDescendantsNotOnlyDirectChildren() {
        val x0=NodeId("x0");val x1=NodeId("x1");val x2=NodeId("x2")
        val innerG=NodeId("innerG");val left=NodeId("left");val right=NodeId("right")
        val imply=NodeId("imply");val root=NodeId("root")
        val common=listOf(LiteralNode(x0,"x0"),LiteralNode(x1,"x1"),
            UnaryNode(innerG,UnaryOperator.G,x1),BinaryNode(left,BinaryOperator.AND,x0,innerG))
        val antecedent=plan("weakening/weaken_antecedent/weaken_antecedent_10_10_10.trace",2)
        val consequent=plan("weakening/weaken_consequent/weaken_consequent_10_10_10.trace",3)
        val badA=FormulaDag(root,common+listOf(BinaryNode(imply,BinaryOperator.IMPLIES,left,x1),
            UnaryNode(root,UnaryOperator.G,imply)))
        val badC=FormulaDag(root,common+listOf(LiteralNode(x2,"x2"),BinaryNode(right,BinaryOperator.AND,x1,x2),
            BinaryNode(imply,BinaryOperator.IMPLIES,left,right),UnaryNode(root,UnaryOperator.G,imply)))
        assertFalse(accepts(antecedent,badA))
        assertFalse(accepts(consequent,badC))
        val goodA=FormulaDag(root,listOf(LiteralNode(x0,"x0"),LiteralNode(x1,"x1"),
            BinaryNode(imply,BinaryOperator.IMPLIES,x0,x1),UnaryNode(root,UnaryOperator.G,imply)))
        val goodC=FormulaDag(root,listOf(LiteralNode(x0,"x0"),LiteralNode(x1,"x1"),LiteralNode(x2,"x2"),
            BinaryNode(right,BinaryOperator.AND,x1,x2),BinaryNode(imply,BinaryOperator.IMPLIES,x0,right),
            UnaryNode(root,UnaryOperator.G,imply)))
        assertTrue(accepts(antecedent,goodA))
        assertTrue(accepts(consequent,goodC))
    }
}
