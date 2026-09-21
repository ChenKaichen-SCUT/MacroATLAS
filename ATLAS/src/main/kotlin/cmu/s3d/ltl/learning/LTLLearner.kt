package cmu.s3d.ltl.learning

import cmu.s3d.ltl.LassoTrace
import edu.mit.csail.sdg.alloy4.A4Reporter
import edu.mit.csail.sdg.parser.CompUtil
import edu.mit.csail.sdg.translator.A4Options
import edu.mit.csail.sdg.translator.TranslateAlloyToKodkod
import kotlin.math.max
import kotlin.math.min

class LTLLearner(
    private val literals: List<String>,
    private val positiveExamples: List<LassoTrace>,
    private val negativeExamples: List<LassoTrace>,
    private val maxNumOfNode: Int,
    private val excludedOperators: List<String> = emptyList(),
    private val customConstraints: String = "",
    customAlloyOptions: A4Options? = null,
    private val minimized: Boolean = true,
) : AlloyMaxBase(customAlloyOptions) {
    fun generateAlloyModel(): String {
        val binaryOp = listOf("And", "Or", "Imply", "Until").filter { !excludedOperators.contains(it) }
        val unaryOp = listOf("Neg", "F", "G", "X").filter { !excludedOperators.contains(it) }

        val maxExampleLength = max(
            positiveExamples.maxOfOrNull { it.length() } ?: 0,
            negativeExamples.maxOfOrNull { it.length() } ?: 0
        )
        val positiveTraces = positiveExamples.mapIndexed { i, example ->
            generateTrace("PT$i", "PositiveTrace", example)
        }
        val negativeTraces = negativeExamples.mapIndexed { i, example ->
            generateTrace("NT$i", "NegativeTrace", example)
        }

        val alloyScript = """
            open util/ordering[SeqIdx]

            abstract sig DAGNode {
            	l: set DAGNode,
            	r: set DAGNode
            }
            fact {
            	all n: DAGNode | n not in n.^(l + r)
            }
            ${
                if (binaryOp.isEmpty())
                    ""
                else
                    """
            sig ${binaryOp.joinToString(", ")} extends DAGNode {} {
            	one l
            	one r
            }"""
            }
            ${
                if (unaryOp.isEmpty())
                    ""
                else
                    """
            sig ${unaryOp.joinToString(", ")} extends DAGNode {} {
                one l
                no r
            }"""
            }
            abstract sig Literal extends DAGNode {} {
            	no l
            	no r
            }

            abstract sig SeqIdx {}
            abstract sig Trace {
            	lasso: SeqIdx -> SeqIdx,
            	valuation: DAGNode -> SeqIdx
            } {
            	// Negation
                ${if ("Neg" in unaryOp) "all n: Neg, i: seqRange | n->i in valuation iff n.l->i not in valuation" else ""}
            	// Or
                ${if ("Or" in binaryOp) "all n: Or, i: seqRange | n->i in valuation iff (n.l->i in valuation or n.r->i in valuation)" else ""}
            	// And
                ${if ("And" in binaryOp) "all n: And, i: seqRange | n->i in valuation iff (n.l->i in valuation and n.r->i in valuation)" else ""}
            	// Imply
                ${if ("Imply" in binaryOp) "all n: Imply, i: seqRange | n->i in valuation iff (n.l->i not in valuation or n.r->i in valuation)" else ""}
            	// G
                ${if ("G" in unaryOp) "all n: G, i: seqRange | n->i in valuation iff all i': futureIdx[i] | n.l->i' in valuation" else ""}
                // X
                ${if ("X" in unaryOp) "all n: X, i: seqRange | n->i in valuation iff n.l->i.(next+lasso) in valuation" else ""}
            	// F
                ${if ("F" in unaryOp) "all n: F, i: seqRange | n->i in valuation iff some i': futureIdx[i] | n.l->i' in valuation" else ""}
            	// Until
                ${
                    if ("Until" in binaryOp)
                        """
                all n: Until, i: seqRange | n->i in valuation iff {
                    some i': futureIdx[i] | n.r->i' in valuation
                    n.r->i in valuation or (n.l->i in valuation and n->i.(next+lasso) in valuation)
            	}"""
                    else
                        ""
                }
            }
            fun seqRange[t: Trace]: set SeqIdx {
            	let lastOfTrace = t.lasso.SeqIdx | lastOfTrace.prevs + lastOfTrace
            }
            fun futureIdx[t: Trace, i: SeqIdx]: set SeqIdx {
            	i.^((next :> seqRange[t]) + t.lasso) + i
            }
            ${if (positiveTraces.isNotEmpty()) "abstract sig PositiveTrace extends Trace {}" else ""}
            ${if (negativeTraces.isNotEmpty()) "abstract sig NegativeTrace extends Trace {}" else ""}
            one sig ${literals.joinToString(", ")} extends Literal {}
            one sig ${(0 until maxExampleLength).joinToString(", ") { "T${it}" }} extends SeqIdx {}
            fact {
                first = T0
                next = ${(0 until maxExampleLength-1).joinToString(" + ") { "T${it}->T${it+1}" }}
            }
            ${positiveTraces.joinToString("")}
            ${negativeTraces.joinToString("")}
            one sig LearnedLTL {
                Root: DAGNode
            }
            fun root: one DAGNode { LearnedLTL.Root }
            fun childrenOf[n: DAGNode]: set DAGNode { n.^(l+r) }
            fun childrenAndSelfOf[n: DAGNode]: set DAGNode { n.*(l+r) }
            fun ancestorsOf[n: DAGNode]: set DAGNode { n.~^(l+r) }
            fun ancestorsAndSelfOf[n: DAGNode]: set DAGNode { n.~*(l+r) }
            fun subDAG[n: DAGNode]: DAGNode -> DAGNode { n.*(l+r) <: (l+r) }
            $customConstraints
            run {
                ${if (positiveTraces.isNotEmpty()) "all t: PositiveTrace | root->T0 in t.valuation" else ""}
                ${if (negativeTraces.isNotEmpty()) "all t: NegativeTrace | root->T0 not in t.valuation" else ""}
                ${if (minimized) "minsome l + r" else ""}
            } for %d DAGNode
        """.trimIndent()

        return alloyScript
    }

    private fun generateTrace(name: String, sig: String, example: LassoTrace): String {
        val trueValues = mutableListOf<String>()
        val falseValues = mutableListOf<String>()

        for ((i, s) in example.getTrace().withIndex()) {
            for (l in literals) {
                if (s.values[l] == true) {
                    trueValues.add(("$l->T$i"))
                } else {
                    falseValues.add(("$l->T$i"))
                }
            }
        }

        val lasso = if (example.loop.isEmpty()) {
            "lasso = T${example.prefix.size-1}->T${example.prefix.size-1}"
        } else {
            "lasso = T${example.length()-1}->T${example.prefix.size}"
        }

        return """
            one sig $name extends $sig {} {
                $lasso
                ${if (trueValues.isNotEmpty()) "${trueValues.joinToString(" + ")} in valuation" else ""}
                ${if (falseValues.isNotEmpty()) "no (${falseValues.joinToString(" + ")}) & valuation" else ""}
            }
        """
    }

    fun learn(start: Int? = null, stepSize: Int = 2): LTLLearningSolution? {
        val startNum = start ?: min(max((maxNumOfNode - literals.size) / 2, 3), 6)
        val nodesSeq = (startNum.. maxNumOfNode step stepSize).toMutableList()
        if (nodesSeq.isEmpty() || nodesSeq.last() < maxNumOfNode)
            nodesSeq.add(maxNumOfNode)

        val alloyTemplate = generateAlloyModel()
        for (n in nodesSeq) {
            val alloyScript = String.format(alloyTemplate, n)

            val reporter = A4Reporter.NOP
            val world = CompUtil.parseEverything_fromString(reporter, alloyScript)
            val options = alloyOptions()
            val command = world.allCommands.first()
            val solution = TranslateAlloyToKodkod.execute_command(reporter, world.allReachableSigs, command, options)

            if (solution.satisfiable()) {
                return LTLLearningSolution(this, world, solution, n, stepSize)
            }
        }

        return null
    }


}