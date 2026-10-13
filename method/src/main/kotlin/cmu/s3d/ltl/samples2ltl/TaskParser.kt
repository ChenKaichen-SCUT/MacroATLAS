package cmu.s3d.ltl.samples2ltl

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.State
import cmu.s3d.ltl.learning.LTLLearner
import edu.mit.csail.sdg.translator.A4Options
import kotlin.math.pow

data class Task(
    val literals: List<String>,
    val positiveExamples: List<LassoTrace>,
    val negativeExamples: List<LassoTrace>,
    val excludedOperators: List<String>,
    val maxNumOfOP: Int,
    val expected: List<String>,
    val customConstraints: String?
) {
    fun buildLearner(options: A4Options? = null, minimized: Boolean = true): LTLLearner {
        return LTLLearner(
            literals = literals,
            positiveExamples = positiveExamples,
            negativeExamples = negativeExamples,
            maxNumOfNode = maxNumOfOP + literals.size,
            excludedOperators = excludedOperators,
            customAlloyOptions = options,
            customConstraints = customConstraints?.let { "\n${it.prependIndent("            ")}\n" } ?: "",
            minimized = minimized
        )
    }

    fun numOfPositives(): Int {
        return positiveExamples.size
    }

    fun numOfNegatives(): Int {
        return negativeExamples.size
    }

    fun numOfVariables(): Int {
        return literals.size
    }

    fun maxLengthOfTraces(): Int {
        return (positiveExamples + negativeExamples).maxOf { it.length() }
    }

    fun toCSVString(): String {
        return "${numOfPositives()},${numOfNegatives()},$maxNumOfOP,${numOfVariables()},${maxLengthOfTraces()},\"$expected\""
    }
}

object TaskParser {

    private val operatorMapping = mapOf(
        "G"  to "G",
        "F"  to "F",
        "!"  to "Neg",
        "U"  to "Until",
        "&"  to "And",
        "|"  to "Or",
        "->" to "Imply",
        "X"  to "X",
        "prop" to "prop"
    )

    fun parseTask(task: String): Task {
        val parts = task.split("---")
        val positives = parts[0].trim()
        val negatives = parts[1].trim()
        val operators = parts[2].trim()
        val maxNumOfOP = parts[3].trim().let {
            if (it[0] == '[') {
                // For historical reasons, when it starts with [, it means the max number of node
                it.substring(1, it.length - 1).toInt()
            } else {
                // otherwise, it is the depth
                (2.0).pow(it.toInt()) - 1
            }
        }.toInt()
        val expected = if (parts.size > 4) parts[4].split(';').map { it.trim() } else emptyList()
        val constraints = if (parts.size > 5) parts[5].trim() else null

        val positiveExamples = parseExamples(positives)
        val negativeExamples = parseExamples(negatives)
        val numOfLiterals = let {
            if (positiveExamples.isEmpty())
                negativeExamples.first()
            else
                positiveExamples.first()
        }.getStateAt(0).values.size
        val literals = (0 until numOfLiterals).map { "x$it" }
        return Task(
            literals = literals,
            positiveExamples = positiveExamples,
            negativeExamples = negativeExamples,
            excludedOperators = parseExcludedOperators(operators),
            maxNumOfOP = maxNumOfOP,
            expected = expected,
            customConstraints = constraints
        )
    }

    private fun parseExamples(examples: String): List<LassoTrace> {
        return if (examples.isBlank())
            emptyList()
        else
            examples.lines().map {
                val line = it.trim()
                val parts = line.split("::")
                val trace = parseTrace(parts[0])
                val lasso = if (parts.size == 1) {
                    0
                } else {
                    val ending = parts[1].substringBefore('[')
                    if (ending.isBlank()) 0 else ending.toInt()
                }
                LassoTrace(prefix = trace.subList(0, lasso), loop = trace.subList(lasso, trace.size))
            }
    }

    private fun parseExcludedOperators(operators: String): List<String> {
        val ops = operators.split(",").map { operatorMapping[it.trim()]!! }
        return operatorMapping.values - ops.toSet()
    }

    private fun parseTrace(trace: String): List<State> {
        val states = trace.split(";")
        return states.map { s ->
            val values = s.split(",")
            State(values.indices.associate { "x$it" to (values[it].trim() == "1") })
        }
    }
}