package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.*
import cmu.s3d.ltl.experiment.*
import cmu.s3d.ltl.learning.AlloyMaxBase
import cmu.s3d.ltl.samples2ltl.Task
import cmu.s3d.ltl.samples2ltl.TaskParser
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.dag.*
import edu.mit.csail.sdg.translator.A4Options
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.AfterEach
import java.io.File
import java.util.Random
import kotlin.test.*

class MatchedAtlasTest {
    private val originalLibraryPath=System.getProperty("java.library.path")
    @BeforeEach fun nativeLibraryPath() {
        System.setProperty("java.library.path",originalLibraryPath+File.pathSeparator+File("lib").absolutePath)
    }
    @AfterEach fun restoreLibraryPath() {
        System.setProperty("java.library.path",originalLibraryPath)
    }

    @Test fun nativeAndJavaBackendsMinimizeReachableSizeAndRepairObjective() {
        val task=TaskParser.parseTask(File("src/test/resources/macro/repair.trace").readText())
        val analysis=RecognizedConstraintAnalyzer.analyze(task,2) as MacroTaskAnalysis.Supported
        for(solver in listOf(A4Options.SatSolver.SAT4JMax,A4Options.SatSolver.OpenWBOWeighted)) {
            val options=AlloyMaxBase.defaultAlloyOptions().apply { this.solver=solver }
            fun <Q:Any> compare(plan:MacroConstraintPlan<Q>) {
                val expected=TinyReferenceEnumerator.optimum(plan,task.positiveExamples,task.negativeExamples)!!
                val baseline=MatchedAtlasLearner(task,plan,options).solve(File("target/matched-repair/$solver"))
                val macro=MacroLearner(plan,task.positiveExamples,task.negativeExamples,options).solve()
                assertEquals(2,expected.size)
                assertEquals(expected.size,baseline.dag!!.size())
                assertEquals(expected.size,macro.dag!!.size())
                assertEquals(1,baseline.metadata["objectivePrimary"])
                assertEquals(1,macro.assignment!!.keptEdges)
            }
            compare(analysis.plan)
        }
    }

    @Test fun nextCannotReadPastTheEndOfAShorterTrace() {
        val state=State(mapOf("x0" to true))
        val task=Task(listOf("x0"),listOf(LassoTrace(loop=listOf(state,state))),listOf(LassoTrace(loop=listOf(state))),
            listOf("Until","Neg","F","G","And","Or","Imply"),2,emptyList(),"one sig X0 extends X {} fact { root = X0 }")
        val analysis=RecognizedConstraintAnalyzer.analyze(task,0,3) as MacroTaskAnalysis.Supported
        fun <Q:Any> compare(plan:MacroConstraintPlan<Q>) {
            assertNull(TinyReferenceEnumerator.optimum(plan,task.positiveExamples,task.negativeExamples))
            assertNull(MacroLearner(plan,task.positiveExamples,task.negativeExamples).solve().dag)
            for(solver in listOf(A4Options.SatSolver.SAT4JMax,A4Options.SatSolver.OpenWBOWeighted)) {
                val options=AlloyMaxBase.defaultAlloyOptions().apply { this.solver=solver }
                assertNull(MatchedAtlasLearner(task,plan,options).solve(File("target/matched-next/$solver")).dag)
            }
        }
        compare(analysis.plan)
    }

    @Test fun originalUntilVerifierRequiresEventualRightOperand() {
        val left=NodeId("x0");val right=NodeId("x1");val root=NodeId("u")
        val dag=FormulaDag(root,listOf(LiteralNode(left,"x0"),LiteralNode(right,"x1"),BinaryNode(root,BinaryOperator.UNTIL,left,right)))
        fun state(l:Boolean,r:Boolean)=State(mapOf("x0" to l,"x1" to r))
        assertFalse(ArtifactVerifier.evaluate(dag,LassoTrace(loop=listOf(state(true,false)))))
        assertTrue(ArtifactVerifier.evaluate(dag,LassoTrace(prefix=listOf(state(true,false)),loop=listOf(state(false,true)))))
        assertFalse(ArtifactVerifier.evaluate(dag,LassoTrace(prefix=listOf(state(false,false)),loop=listOf(state(false,true)))))
        assertTrue(ArtifactVerifier.evaluate(dag,LassoTrace(loop=listOf(state(false,true)))))
    }

    @Test fun concreteBinaryBudgetCannotBeSatisfiedByFewerBinaryNodes() {
        val aps=listOf("x0","x1","x2")
        fun trace(bits:List<Boolean>)=LassoTrace(loop=listOf(State(aps.zip(bits).toMap())))
        val task=Task(aps,listOf(trace(listOf(true,true,true))),
            (0..2).map { missing->trace((0..2).map { it!=missing }) },
            listOf("Until","Neg","X","F","G","Or","Imply"),2,emptyList(),null)
        for(b in 0..2) {
            val analysis=RecognizedConstraintAnalyzer.analyze(task,b,5) as MacroTaskAnalysis.Supported
            fun <Q:Any> solve(plan:MacroConstraintPlan<Q>)=MatchedAtlasLearner(task,plan,AlloyMaxBase.defaultAlloyOptions()).solve(File("target/matched-binary/$b"))
            val result=solve(analysis.plan)
            assertEquals(if(b<2)null else 5,result.dag?.size())
        }
    }

    @Test fun matchedConcreteDagEncodingAgreesWithTinyReferenceAndMacro() {
        val random=Random(20260923)
        var sat=0
        for(i in 0 until 80) {
            val aps=if(i%2==0) listOf("x0") else listOf("x0","x1")
            fun trace():LassoTrace {
                val states=(0..random.nextInt(2)).map { State(aps.associateWith { random.nextBoolean() }) }
                return LassoTrace(loop=states)
            }
            val raw=when {
                i>=60 -> "one sig F0 extends F {} fact { root = F0 } fact { x0 in childrenAndSelfOf[root] } fact { maxsome[2] subDAG[root] & (F0->x0) }"
                i%4==0 -> "fact { ${RecognizedConstraintAnalyzer.NNF} }"
                i%4==1 -> "fact { x0 in childrenAndSelfOf[root] }"
                i%4==2 -> "fact { no l & r }"
                else -> null
            }
            val task=Task(aps,listOf(trace()),listOf(trace()),listOf("Until","X","G","Or","Imply"),3,emptyList(),raw)
            val analysis=RecognizedConstraintAnalyzer.analyze(task,i%2,1+i%4) as MacroTaskAnalysis.Supported
            fun <Q:Any> compare(plan:MacroConstraintPlan<Q>) {
                val expected=TinyReferenceEnumerator.optimum(plan,task.positiveExamples,task.negativeExamples)
                val metrics=BackendMetrics()
                val baseline=MatchedAtlasLearner(task,plan,AlloyMaxBase.defaultAlloyOptions(),metrics).solve(File("target/matched-reference/$i"))
                val macro=MacroLearner(plan,task.positiveExamples,task.negativeExamples).solve()
                assertEquals(expected?.size,baseline.dag?.size(),"case $i baseline")
                assertEquals(expected?.size,macro.dag?.size(),"case $i macro")
                if(expected!=null) {
                    assertEquals(expected.kept,baseline.metadata["objectivePrimary"],"case $i repair")
                    assertEquals(expected.kept,macro.assignment!!.keptEdges,"case $i macro repair")
                    sat++
                }
                assertTrue((metrics.metadata()["backendTranslationCount"] as Int)>=0)
            }
            compare(analysis.plan)
        }
        File("target/phase4-matched-reference.txt").writeText("seed=20260923\ntasks=80\nSAT=$sat\nUNSAT=${80-sat}\nobjective mismatches=0\n")
    }
}
