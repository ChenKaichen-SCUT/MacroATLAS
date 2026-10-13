package cmu.s3d.ltl.macro.search

/** AUTO may return a verified bounded SAT witness, but bounded UNSAT is not
 * an UNSAT proof for the original unrestricted task. */
object AutoDomainSafety {
    const val BOUNDED_UNSAT = "BOUNDED_MACRO_UNSAT"
    const val TEMPLATE_MINIMUM = "BINARY_BUDGET_BELOW_TEMPLATE_MINIMUM"

    /** Avoid a solver call when the recognized syntax already exceeds b. */
    fun precheck(analysis: MacroTaskAnalysis.Supported): String? =
        if ("OfficialWeakeningConsequent" in analysis.recognizedFeatures && analysis.plan.binaryBudget < 3)
            TEMPLATE_MINIMUM else null
}
