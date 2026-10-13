package cmu.s3d.ltl.macro.fiber

import cmu.s3d.ltl.macro.unary.UnaryWord

/** Immutable shortest syntax witness for a fiber, not necessarily a canonical word. */
data class FiberRepresentative(val word: UnaryWord) {
    /** Derived from the word, so a witness cannot carry an inconsistent length. */
    val length: Int get() = word.length
}
