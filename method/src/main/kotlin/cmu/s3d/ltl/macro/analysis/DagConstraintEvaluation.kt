package cmu.s3d.ltl.macro.analysis

import cmu.s3d.ltl.macro.dag.NodeId
import cmu.s3d.ltl.macro.dag.immutableMap

/** Immutable per-node constraint states, including nonaccepting states. */
class DagConstraintEvaluation<Q : Any>(stateByNode: Map<NodeId, Q>, val rootState: Q) {
    /** One value for each full DAG identity. Q obeys the Phase 1 immutable-state contract. */
    val stateByNode: Map<NodeId, Q> = immutableMap(stateByNode.toSortedMap())
}
