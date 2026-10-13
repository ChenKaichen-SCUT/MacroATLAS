package cmu.s3d.ltl.macro.search

class UnsupportedMacroTaskException(val analysis: MacroTaskAnalysis.Unsupported) : IllegalArgumentException(
    "Macro unsupported: ${analysis.reasons}: ${analysis.detail}"
)

/** Only a capability result can select AUTO fallback. Solver/decoder/verifier exceptions propagate. */
object MacroTaskDispatcher {
    fun <T> run(mode: MacroSolverMode, analyze: () -> MacroTaskAnalysis, original: () -> T,
                macro: (MacroTaskAnalysis.Supported) -> T, onUnsupported: (MacroTaskAnalysis.Unsupported) -> Unit = {}): T {
        if (mode == MacroSolverMode.OFF) return original()
        return when (val result = analyze()) {
            is MacroTaskAnalysis.Supported -> macro(result)
            is MacroTaskAnalysis.Unsupported -> {
                onUnsupported(result)
                if (mode == MacroSolverMode.FORCE) throw UnsupportedMacroTaskException(result)
                original()
            }
        }
    }
}
