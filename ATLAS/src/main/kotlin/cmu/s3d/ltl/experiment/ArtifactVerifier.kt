package cmu.s3d.ltl.experiment

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.samples2ltl.Task

/** The artifact sometimes contains incomplete valuations; these are not concrete traces. */
class InvalidArtifactTraceException(message: String): IllegalArgumentException(message)

/** Independent concrete lasso evaluator for Original ATLAS, including U. Does not normalize. */
object ArtifactVerifier {
    fun requireConcreteInput(task: Task) {
        for ((index, trace) in (task.positiveExamples + task.negativeExamples).withIndex()) {
            if (trace.length() == 0) throw InvalidArtifactTraceException("Empty trace $index")
            for ((position, state) in trace.getTrace().withIndex()) {
                if (state.values.keys != task.literals.toSet()) {
                    throw InvalidArtifactTraceException("Trace $index state $position: expected ${task.literals.size} propositions, got ${state.values.size}; original input preserved")
                }
            }
        }
    }

    fun evaluate(dag: FormulaDag, trace: LassoTrace): Boolean {
        val size=trace.length();require(size>0)
        fun next(i:Int)=if(i+1<size)i+1 else if(trace.loop.isEmpty())size-1 else trace.prefix.size
        val values=hashMapOf<NodeId,BooleanArray>()
        fun fixed(seed:Boolean,step:(Int,BooleanArray)->Boolean):BooleanArray {
            var current=BooleanArray(size){seed}
            do {val old=current;current=BooleanArray(size){step(it,old)}}while(!current.contentEquals(old))
            return current
        }
        for(id in dag.postOrder()) values[id]=when(val n=dag.node(id)) {
            is LiteralNode -> BooleanArray(size){trace.getStateAt(it).values.getValue(n.proposition)}
            is UnaryNode -> {val c=values.getValue(n.child);when(n.operator) {
                UnaryOperator.NOT -> BooleanArray(size){!c[it]}
                UnaryOperator.X -> BooleanArray(size){c[next(it)]}
                UnaryOperator.F -> fixed(false){i,v->c[i]||v[next(i)]}
                UnaryOperator.G -> fixed(true){i,v->c[i]&&v[next(i)]}
            }}
            is BinaryNode -> {val l=values.getValue(n.left);val r=values.getValue(n.right);when(n.operator) {
                BinaryOperator.AND -> BooleanArray(size){l[it]&&r[it]}
                BinaryOperator.OR -> BooleanArray(size){l[it]||r[it]}
                BinaryOperator.IMPLIES -> BooleanArray(size){!l[it]||r[it]}
                BinaryOperator.UNTIL -> fixed(false){i,v->r[i]||(l[i]&&v[next(i)])}
            }}
        }
        return values.getValue(dag.root)[0]
    }
}
