package cmu.s3d.ltl.macro.dag

/** Validated, rooted immutable DAG. All nodes must be reachable; no nodes are silently removed. */
class FormulaDag(val root: NodeId, nodes: Map<NodeId, FormulaNode>) {
    /** Defensive snapshot sorted by complete node identity. */
    val nodes: Map<NodeId, FormulaNode> = immutableMap(nodes.toSortedMap())
    private val order = FormulaDagValidator.validate(root, this.nodes)
    private val parentSets: Map<NodeId, Set<NodeId>>
    private val incoming: Map<NodeId, Int>

    init {
        val parents = this.nodes.keys.associateWith { sortedSetOf<NodeId>() }
        val counts = this.nodes.keys.associateWith { 0 }.toMutableMap()
        for ((id, node) in this.nodes) for (child in node.children()) {
            parents.getValue(child).add(id)
            counts[child] = counts.getValue(child) + 1
        }
        parentSets = immutableMap(parents.mapValues { immutableSet(it.value) })
        incoming = immutableMap(counts)
    }

    /** Collection constructor detects duplicate NodeIds before building a map. */
    constructor(root: NodeId, nodes: Collection<FormulaNode>) : this(root, uniqueNodes(nodes))

    /** Look up an exact identity, failing on an unknown node. */
    fun node(id: NodeId): FormulaNode = nodes[id] ?: throw IllegalArgumentException("Unknown node: $id")

    /** Children in CHILD or LEFT, RIGHT order, preserving duplicate references. */
    fun children(id: NodeId): List<NodeId> = node(id).children()

    /** Distinct parent identities, sorted independently of input map order. */
    fun parents(id: NodeId): Set<NodeId> = parentSets[id] ?: throw IllegalArgumentException("Unknown node: $id")

    /**
     * Incoming PORT count, not distinct parent count: b.left == b.right contributes
     * two edges and must protect a shared unary child from being copied on expansion.
     */
    fun indegree(id: NodeId): Int = incoming[id] ?: throw IllegalArgumentException("Unknown node: $id")

    /** Every stored identity; validity ensures all are reachable from root. */
    fun reachableNodes(): Set<NodeId> = nodes.keys

    /** Memoized deterministic postorder; each shared node occurs exactly once. */
    fun postOrder(): List<NodeId> = order

    /** Number of actual formula nodes. */
    fun size(): Int = nodes.size

    /** Exact graph equality, including root, identities, labels and ordered references. */
    override fun equals(other: Any?): Boolean = other is FormulaDag && root == other.root && nodes == other.nodes

    /** Hash consistent with exact graph equality. */
    override fun hashCode(): Int = 31 * root.hashCode() + nodes.hashCode()

    /** A finite identity-based description that does not recursively expand sharing. */
    override fun toString(): String = "FormulaDag(root=$root, nodes=${nodes.values})"

    companion object {
        private fun uniqueNodes(nodes: Collection<FormulaNode>): Map<NodeId, FormulaNode> {
            val result = LinkedHashMap<NodeId, FormulaNode>()
            for (node in nodes) require(result.put(node.id, node) == null) { "Duplicate NodeId: ${node.id}" }
            return result
        }
    }
}
