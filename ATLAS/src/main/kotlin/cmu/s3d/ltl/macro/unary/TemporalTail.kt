package cmu.s3d.ltl.macro.unary

/** Canonical temporal tails; FG means F(G(hole)), and GF means G(F(hole)). */
enum class TemporalTail {
    ID, F, G, FG, GF;

    /** Tail obtained when pushing an outer negation through the temporal operators. */
    fun dual(): TemporalTail = when (this) {
        ID -> ID
        F -> G
        G -> F
        FG -> GF
        GF -> FG
    }
}
