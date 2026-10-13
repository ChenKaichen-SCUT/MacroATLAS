package cmu.s3d.ltl.experiment

import edu.mit.csail.sdg.alloy4.A4Reporter

/** Alloy exposes total variables/clauses, not a trustworthy hard/soft clause split. */
class BackendMetrics : A4Reporter() {
    private val passes = arrayListOf<Triple<Int,Int,Int>>()
    override fun solve(primaryVars: Int, totalVars: Int, clauses: Int) { passes.add(Triple(primaryVars,totalVars,clauses)) }
    fun metadata(): Map<String, Any> = mapOf(
        "backendTranslationCount" to passes.size,
        "primaryVars" to (passes.maxOfOrNull { it.first } ?: 0),
        "vars" to (passes.maxOfOrNull { it.second } ?: 0),
        "backendTotalClauses" to (passes.maxOfOrNull { it.third } ?: 0)
    )
}
