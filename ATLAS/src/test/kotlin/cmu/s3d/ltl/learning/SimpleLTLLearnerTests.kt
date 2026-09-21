package cmu.s3d.ltl.learning

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.State
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals

class SimpleLTLLearnerTests {
    @Test
    fun testSimpleG() {
        val learner = LTLLearner(
            literals = listOf("X0", "X1"),
            positiveExamples = listOf(
                // 1,1;1,1;0,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to true, "X1" to true)),
                        State(mapOf("X0" to true, "X1" to true)),
                        State(mapOf("X0" to false, "X1" to true)),
                    )
                ),
                // 0,1;1,1;0,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to true)),
                        State(mapOf("X0" to true, "X1" to true)),
                        State(mapOf("X0" to false, "X1" to true)),
                    )
                ),
                // 0,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to true)),
                    )
                ),
            ),
            negativeExamples = listOf(
                // 0,0;0,0;0,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to false)),
                        State(mapOf("X0" to false, "X1" to false)),
                        State(mapOf("X0" to false, "X1" to true)),
                    )
                ),
                // 0,1;0,0;1,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to true)),
                        State(mapOf("X0" to false, "X1" to false)),
                        State(mapOf("X0" to true, "X1" to true)),
                    )
                ),
            ),
            maxNumOfNode = 3,
            excludedOperators = listOf("F", "Until"),
        )
        assertEquals(
            """
                open util/ordering[SeqIdx]

                abstract sig DAGNode {
                	l: set DAGNode,
                	r: set DAGNode
                }
                fact {
                	all n: DAGNode | n not in n.^(l + r)
                }

                sig And, Or, Imply extends DAGNode {} {
                	one l
                	one r
                }

                sig Neg, G, X extends DAGNode {} {
                    one l
                    no r
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
                    all n: Neg, i: seqRange | n->i in valuation iff n.l->i not in valuation
                	// Or
                    all n: Or, i: seqRange | n->i in valuation iff (n.l->i in valuation or n.r->i in valuation)
                	// And
                    all n: And, i: seqRange | n->i in valuation iff (n.l->i in valuation and n.r->i in valuation)
                	// Imply
                    all n: Imply, i: seqRange | n->i in valuation iff (n.l->i not in valuation or n.r->i in valuation)
                	// G
                    all n: G, i: seqRange | n->i in valuation iff all i': futureIdx[i] | n.l->i' in valuation
                    // X
                    all n: X, i: seqRange | n->i in valuation iff n.l->i.(next+lasso) in valuation
                	// F
                    
                	// Until
                    
                }
                fun seqRange[t: Trace]: set SeqIdx {
                	let lastOfTrace = t.lasso.SeqIdx | lastOfTrace.prevs + lastOfTrace
                }
                fun futureIdx[t: Trace, i: SeqIdx]: set SeqIdx {
                	i.^((next :> seqRange[t]) + t.lasso) + i
                }
                abstract sig PositiveTrace extends Trace {}
                abstract sig NegativeTrace extends Trace {}
                one sig X0, X1 extends Literal {}
                one sig T0, T1, T2 extends SeqIdx {}
                fact {
                    first = T0
                    next = T0->T1 + T1->T2
                }

                one sig PT0 extends PositiveTrace {} {
                    lasso = T2->T0
                    X0->T0 + X1->T0 + X0->T1 + X1->T1 + X1->T2 in valuation
                    no (X0->T2) & valuation
                }

                one sig PT1 extends PositiveTrace {} {
                    lasso = T2->T0
                    X1->T0 + X0->T1 + X1->T1 + X1->T2 in valuation
                    no (X0->T0 + X0->T2) & valuation
                }

                one sig PT2 extends PositiveTrace {} {
                    lasso = T0->T0
                    X1->T0 in valuation
                    no (X0->T0) & valuation
                }


                one sig NT0 extends NegativeTrace {} {
                    lasso = T2->T0
                    X1->T2 in valuation
                    no (X0->T0 + X1->T0 + X0->T1 + X1->T1 + X0->T2) & valuation
                }

                one sig NT1 extends NegativeTrace {} {
                    lasso = T2->T0
                    X1->T0 + X0->T2 + X1->T2 in valuation
                    no (X0->T0 + X0->T1 + X1->T1) & valuation
                }

                one sig LearnedLTL {
                    Root: DAGNode
                }
                fun root: one DAGNode { LearnedLTL.Root }
                fun childrenOf[n: DAGNode]: set DAGNode { n.^(l+r) }
                fun childrenAndSelfOf[n: DAGNode]: set DAGNode { n.*(l+r) }
                fun ancestorsOf[n: DAGNode]: set DAGNode { n.~^(l+r) }
                fun ancestorsAndSelfOf[n: DAGNode]: set DAGNode { n.~*(l+r) }
                fun subDAG[n: DAGNode]: DAGNode -> DAGNode { n.*(l+r) <: (l+r) }
                
                run {
                    all t: PositiveTrace | root->T0 in t.valuation
                    all t: NegativeTrace | root->T0 not in t.valuation
                    minsome l + r
                } for %d DAGNode
            """.trimIndent(),
            learner.generateAlloyModel().trimIndent()
        )

        val solution = learner.learn()
        assert(solution != null)
        assertEquals(
            "(G X1)",
            solution!!.getLTL()
        )
    }

    @Test
    fun testSimpleUntil() {
        val learner = LTLLearner(
            literals = listOf("X0", "X1"),
            positiveExamples = listOf(
                // 1,1;1,0;0,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to true, "X1" to true)),
                        State(mapOf("X0" to true, "X1" to false)),
                        State(mapOf("X0" to false, "X1" to true)),
                    )
                ),
                // 0,1;1,1;0,0
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to true)),
                        State(mapOf("X0" to true, "X1" to true)),
                        State(mapOf("X0" to false, "X1" to false)),
                    )
                ),
                // 1,1;0,0;0,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to true, "X1" to true)),
                        State(mapOf("X0" to false, "X1" to false)),
                        State(mapOf("X0" to false, "X1" to true)),
                    )
                ),
                // 1,0;1,0;1,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to true, "X1" to false)),
                        State(mapOf("X0" to true, "X1" to false)),
                        State(mapOf("X0" to true, "X1" to true)),
                    )
                ),
            ),
            negativeExamples = listOf(
                // 0,0
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to false)),
                    )
                ),
                // 0,0;0,0;1,1
                LassoTrace(
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to false)),
                        State(mapOf("X0" to false, "X1" to false)),
                        State(mapOf("X0" to true, "X1" to true)),
                    )
                ),
                // 1,0;0,0::1
                LassoTrace(
                    prefix = listOf(
                        State(mapOf("X0" to true, "X1" to false)),
                    ),
                    loop = listOf(
                        State(mapOf("X0" to false, "X1" to false)),
                    )
                ),
            ),
            maxNumOfNode = 3,
        )

        val solution = learner.learn()
        assert(solution != null)
        assertEquals(
            "(Until X0 X1)",
            solution!!.getLTL()
        )
    }
}