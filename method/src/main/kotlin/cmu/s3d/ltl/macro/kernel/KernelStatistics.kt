package cmu.s3d.ltl.macro.kernel

import cmu.s3d.ltl.macro.dag.*

/** Concrete counts only; these are correctness instrumentation, not solver slots or timing claims. */
data class KernelStatistics(
    val b: Int,
    val p: Int,
    val u: Int,
    val numberOfAnchors: Int,
    val numberOfPorts: Int,
    val numberOfMacroEdges: Int,
    val maxOriginalUnaryLength: Int,
    val originalNodeCount: Int,
    val canonicalNodeCount: Int
) {
    /** Conservative port budget, with all explicitly protected nodes counted in p. */
    val kernelBudget: Long get() = p.toLong() + 3L * b + 2

    /** Enforce the port identity and the O(b+p) bound without relying on JVM -ea. */
    fun validatePortBudget() {
        check(numberOfPorts.toLong() == 1L + 2L * b + u) { "Port arity count is inconsistent" }
        check(numberOfPorts == numberOfMacroEdges) { "Each port must have exactly one edge" }
        check(numberOfPorts <= kernelBudget) { "Port count exceeds p + 3b + 2" }
    }
}

internal fun kernelStatistics(
    anchors: Map<NodeId, FormulaNode>, protected: Set<NodeId>, edges: Collection<RawMacroEdge>,
    originalCount: Int, canonicalCount: Int
): KernelStatistics = KernelStatistics(
    anchors.values.count { it is BinaryNode }, protected.size, anchors.values.count { it is UnaryNode },
    anchors.size, portsOf(anchors).size, edges.size, edges.maxOfOrNull { it.originalWord.length } ?: 0,
    originalCount, canonicalCount
)
