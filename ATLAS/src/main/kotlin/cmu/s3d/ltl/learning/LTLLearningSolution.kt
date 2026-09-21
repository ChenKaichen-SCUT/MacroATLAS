package cmu.s3d.ltl.learning

import edu.mit.csail.sdg.parser.CompModule
import edu.mit.csail.sdg.parser.CompUtil
import edu.mit.csail.sdg.translator.A4Solution
import edu.mit.csail.sdg.translator.A4TupleSet

class LTLLearningSolution(
    private val learner: LTLLearner,
    private val world: CompModule,
    private val alloySolution: A4Solution,
    private val numOfNode: Int,
    private val stepSize: Int
) {

    init {
        for (a in alloySolution.allAtoms)
            world.addGlobal(a.label, a)
        for (a in alloySolution.allSkolems)
            world.addGlobal(a.label, a)
    }

    data class Node(val name: String, val left: String?, val right: String?)

    private val operatorMapping = mapOf(
        "G"  to "G",
        "F"  to "F",
        "Neg"  to "!",
        "Until"  to "U",
        "And"  to "&",
        "Or"  to "|",
        "Imply" to "->",
        "X"  to "X"
    )

    fun getLTL(): String {
        val root = getRoot()
        return getLTL(root)
    }

    fun getLTL2(): String {
        val root = getRoot()
        return getLTL2(root)
    }

    private fun getLTL(node: String): String {
        val (name, leftNode, rightNode) = getNodeAndChildren(node)
        val sigName = name.replace("\\d+$".toRegex(), "")
        return when {
            leftNode == null && rightNode == null -> name
            leftNode != null && rightNode == null -> "($sigName ${getLTL(leftNode)})"
            leftNode != null && rightNode != null -> "($sigName ${getLTL(leftNode)} ${getLTL(rightNode)})"
            else -> error("Invalid LTL formula.")
        }
    }

    private fun getLTL2(node: String): String {
        val (name, leftNode, rightNode) = getNodeAndChildren(node)
        return when {
            leftNode == null && rightNode == null -> name
            leftNode != null && rightNode == null -> "${getMappedOperator(name)}(${getLTL2(leftNode)})"
            leftNode != null && rightNode != null -> "${getMappedOperator(name)}(${getLTL2(leftNode)},${getLTL2(rightNode)})"
            else -> error("Invalid LTL formula.")
        }
    }

    private fun getMappedOperator(name: String): String {
        return operatorMapping[name.replace("\\d+$".toRegex(), "")] ?: error("Invalid operator: $name")
    }

    fun getNodeAndChildren(node: String): Node {
        val name = node.split('$')[0]
        val leftExpr = CompUtil.parseOneExpression_fromString(world, "$node.l")
        val leftNode = (alloySolution.eval(leftExpr) as A4TupleSet).map { it.atom(0) }.firstOrNull()
        val rightExpr = CompUtil.parseOneExpression_fromString(world, "$node.r")
        val rightNode = (alloySolution.eval(rightExpr) as A4TupleSet).map { it.atom(0) }.firstOrNull()
        return Node(name, leftNode, rightNode)
    }

    fun getRoot(): String {
        val expr = CompUtil.parseOneExpression_fromString(world, "root")
        return (alloySolution.eval(expr) as A4TupleSet).map { it.atom(0) }.first()
    }

    fun next(): LTLLearningSolution? {
        val nextSolution = alloySolution.next()
        return if (nextSolution.satisfiable()) {
            LTLLearningSolution(learner, world, nextSolution, numOfNode, stepSize)
        } else {
            learner.learn(numOfNode + stepSize)
        }
    }
}