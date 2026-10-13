package cmu.s3d.ltl.experiment

import cmu.s3d.ltl.LassoTrace
import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.dag.*
import cmu.s3d.ltl.macro.unary.UnaryOperator
import cmu.s3d.ltl.samples2ltl.Task

/** Independent lasso evaluator using Original ATLAS input semantics, including U. */
object ArtifactVerifier {
    fun inputDiagnostics(task: Task): Map<String, Any> {
        val declared = task.literals.toSet()
        val states = (task.positiveExamples + task.negativeExamples).flatMap { it.getTrace() }
        return mapOf("policy" to "Original LTLLearner.generateTrace: missing declared values are false; undeclared columns ignored; source bytes unchanged",
            "statesWithMissingValues" to states.count { !it.values.keys.containsAll(declared) },
            "missingValues" to states.sumOf { (declared - it.values.keys).size },
            "ignoredExtraValues" to states.sumOf { (it.values.keys - declared).size })
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
            // Exactly the input interpretation in LTLLearner.generateTrace, without editing the trace.
            is LiteralNode -> BooleanArray(size){trace.getStateAt(it).values[n.proposition] == true}
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
