package cmu.s3d.ltl.learning

import cmu.s3d.ltl.LassoTrace

class SampleReducer(
    private val positiveSamples: List<LassoTrace>,
    private val negativeSamples: List<LassoTrace>
) {
    /**
     * Reduce the representation of a sample:
     *  - Remove duplicates in the lasso (e.g., 'abab' is reduced to 'ab')
     *  - Remove redundant information in the prefix part (e.g., ab{aab} is reduced to {aba})
     */
    fun reduceSample(): Pair<List<LassoTrace>, List<LassoTrace>> {
        val positives = positiveSamples.map { reduce(it) }
        val negatives = negativeSamples.map { reduce(it) }
        return Pair(positives, negatives)
    }

    private fun reduce(example: LassoTrace): LassoTrace {
        if (example.loop.isEmpty()) return example

        var reduced = example
        // reduce duplicates in the lasso
        for (l in 1..(reduced.loop.size / 2)) {
            if (reduced.loop.size % l == 0) {
                var duplicated = true
                for (j in l until reduced.loop.size) {
                    if (reduced.loop[j] != reduced.loop[j % l]) {
                        duplicated = false
                        break
                    }
                }
                if (duplicated) {
                    reduced = LassoTrace(reduced.prefix, reduced.loop.subList(0, l))
                    break
                }
            }
        }
        // reduce prefix
        var i = reduced.prefix.size - 1
        while (i >= 0) {
            if (reduced.prefix.last() == reduced.loop.last()) {
                reduced = LassoTrace(
                    prefix = reduced.prefix.subList(0, i),
                    loop = listOf(reduced.prefix.last()) + reduced.loop.subList(0, reduced.loop.size - 1)
                )
                i--
            } else {
                break
            }
        }
        return reduced
    }
}