package cmu.s3d.ltl.experiment

import cmu.s3d.ltl.samples2ltl.TaskParser
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.unary.UnaryOperator
import java.io.File
import org.junit.jupiter.api.Test
import kotlin.test.*

class ArtifactInputTests {
    @Test fun officialVotingFormulaVerifiesUnderOriginalMissingValueSemantics() {
        val file = File("benchmark/voting_machine/voting5.trace")
        val original = file.readText()
        val task = TaskParser.parseTask(original)
        val l = NodeId("x5"); val r = NodeId("x8"); val implication = NodeId("imply"); val root = NodeId("g")
        val dag = FormulaDag(root, listOf(LiteralNode(l,"x5"), LiteralNode(r,"x8"),
            BinaryNode(implication,BinaryOperator.IMPLIES,l,r), UnaryNode(root,UnaryOperator.G,implication)))
        assertTrue(task.positiveExamples.all { ArtifactVerifier.evaluate(dag,it) })
        assertTrue(task.negativeExamples.none { ArtifactVerifier.evaluate(dag,it) })
        assertTrue(ArtifactVerifier.inputDiagnostics(task).getValue("missingValues") as Int > 0)
        // An incorrect constant-like candidate still fails classification on this same input.
        val wrong = FormulaDag(l, listOf(LiteralNode(l,"x5")))
        assertFalse(task.positiveExamples.all { ArtifactVerifier.evaluate(wrong,it) })
        assertEquals(original, file.readText())
    }

    @Test fun missingFalseAndIgnoredExtraColumnsAgreeWithOriginalModel() {
        val task = TaskParser.parseTask("1,0;0;0,1,1::0\n---\n0,0::0\n---\nG,F,!,U,&,|,->,X\n---\n2\n")
        val model = task.buildLearner().generateAlloyModel()
        assertTrue(model.contains("x1->T1"))
        assertFalse(model.contains("x2->"))
        val id = NodeId("x1")
        val dag = FormulaDag(id, listOf(LiteralNode(id,"x1")))
        assertFalse(ArtifactVerifier.evaluate(dag, cmu.s3d.ltl.LassoTrace(loop=listOf(task.positiveExamples[0].getStateAt(1)))))
        assertTrue(ArtifactVerifier.evaluate(dag, cmu.s3d.ltl.LassoTrace(loop=listOf(task.positiveExamples[0].getStateAt(2)))))
        assertEquals(1, ArtifactVerifier.inputDiagnostics(task)["missingValues"])
        assertEquals(1, ArtifactVerifier.inputDiagnostics(task)["ignoredExtraValues"])
    }
}
