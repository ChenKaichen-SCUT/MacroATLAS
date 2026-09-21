package cmu.s3d.ltl.macro.dag

/** Complete node identity (for example G$0), separate from its operator/proposition label. */
data class NodeId(val value: String) : Comparable<NodeId> {
    init { require(value.isNotBlank()) { "NodeId must not be blank" } }

    /** Stable order independent of map insertion order. */
    override fun compareTo(other: NodeId): Int = value.compareTo(other.value)

    /** Display the full identity without dropping an Alloy atom suffix. */
    override fun toString(): String = value
}
