package cmu.s3d.ltl.samples2ltl

import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotEquals

class TaskParserTests {
    @Test
    fun testExample0000() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0000.trace").readText()
        val task = TaskParser.parseTask(content)

        assertEquals(5, task.numOfPositives())
        assertEquals(5, task.numOfNegatives())
        assertEquals(3, task.maxNumOfOP)
        assertEquals(2, task.numOfVariables())
        assertEquals(5, task.maxLengthOfTraces())
        assertEquals(listOf("G(!(x0))", "!(F(x0))"), task.expected)

        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "!(F(x0))",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testExample0001() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0001.trace").readText()
        val task = TaskParser.parseTask(content)

        assertEquals(5, task.numOfPositives())
        assertEquals(5, task.numOfNegatives())
        assertEquals(3, task.maxNumOfOP)
        assertEquals(2, task.numOfVariables())
        assertEquals(5, task.maxLengthOfTraces())
        assertEquals(listOf("G(!(x0))"), task.expected)
        assertEquals("fact {\n    root in G\n}", task.customConstraints)

        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "G(!(x0))",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testExample0002() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0002.trace").readText()
        val task = TaskParser.parseTask(content)

        assertEquals(0, task.numOfPositives())
        assertEquals(5, task.numOfNegatives())
        assertEquals(3, task.maxNumOfOP)
        assertEquals(2, task.numOfVariables())
        assertEquals(5, task.maxLengthOfTraces())
        assertEquals(listOf("G(!(x0))"), task.expected)

        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "G(x0)",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testExample0003() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0003.trace").readText()
        val task = TaskParser.parseTask(content)

        assertEquals(5, task.numOfPositives())
        assertEquals(0, task.numOfNegatives())
        assertEquals(3, task.maxNumOfOP)
        assertEquals(2, task.numOfVariables())
        assertEquals(5, task.maxLengthOfTraces())
        assertEquals(listOf("G(!(x0))"), task.expected)

        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "->(x1,x1)",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testExample0004() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0004.trace").readText()
        val task = TaskParser.parseTask(content)

        assertEquals(5, task.numOfPositives())
        assertEquals(0, task.numOfNegatives())
        assertEquals(3, task.maxNumOfOP)
        assertEquals(2, task.numOfVariables())
        assertEquals(5, task.maxLengthOfTraces())
        assertEquals(listOf("G(!(x0))"), task.expected)

        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "F(x1)",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testExample0005() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0005.trace").readText()
        val task = TaskParser.parseTask(content)

        assertEquals(5, task.numOfPositives())
        assertEquals(5, task.numOfNegatives())
        assertEquals(3, task.maxNumOfOP)
        assertEquals(2, task.numOfVariables())
        assertEquals(5, task.maxLengthOfTraces())
        assertEquals(listOf("G(!(x0))"), task.expected)

        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "!(F(x0))",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testExample0006() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0006.trace").readText()
        val task = TaskParser.parseTask(content)

        assertEquals(5, task.numOfPositives())
        assertEquals(5, task.numOfNegatives())
        assertEquals(2, task.maxNumOfOP)
        assertEquals(2, task.numOfVariables())
        assertEquals(5, task.maxLengthOfTraces())
        assertEquals(listOf("G(!(x0))"), task.expected)

        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "!(F(x0))",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testf_01_nw_010_type_0() {
        val content = ClassLoader.getSystemResource("samples2ltl/f_01-nw_010-ml_06-0.type-0.trace").readText()
        val task = TaskParser.parseTask(content)
        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "G(!(x0))",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testExample0007() {
        val content = ClassLoader.getSystemResource("samples2ltl/example0007.trace").readText()
        val task = TaskParser.parseTask(content)
        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertEquals(
            "U(x0,x1)",
            solution!!.getLTL2()
        )
    }

    @Test
    fun testBase0007() {
        val content = ClassLoader.getSystemResource("samples2ltl/base/0007.trace").readText()
        val task = TaskParser.parseTask(content)
        val solution = task.buildLearner().learn()
        assert(solution != null)
        assertNotEquals(
            "U(->(x2,x2),!(->(x2,x2)))",
            solution!!.getLTL2()
        )
    }
}