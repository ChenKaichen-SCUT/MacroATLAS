package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.macro.constraint.BinaryOperator
import cmu.s3d.ltl.macro.kernel.PortKind
import cmu.s3d.ltl.macro.unary.*

/** Direct macro encoding. Units count size; they are not syntax nodes and have no labels or valuations. */
class MacroAlloyModelBuilder<Q : Any>(val context: MacroCompilationContext<Q>) {
    private val p = context.plan
    val k = p.anchorSlotBudget
    val portNames = listOf("R") + (0 until k).flatMap { listOf("C$it", "L$it", "D$it") }
    val offsets = context.positions.runningFold(0) { n, pos -> n + pos.successor.size }.dropLast(1)
    val positionCount = context.positions.sumOf { it.successor.size }
    private fun union(values: Iterable<String>) = values.joinToString(" + ").ifEmpty { "none" }
    private fun labelSet(test: (MacroLabel) -> Boolean) = union(p.labels.indices.filter { test(p.labels[it]) }.map { "T$it" })
    private fun slot(id: cmu.s3d.ltl.macro.dag.NodeId) = "A${p.protectedIdentities.indexOfFirst { it.id == id }.also { require(it >= 0) }}"
    private fun port(source: cmu.s3d.ltl.macro.dag.NodeId, kind: PortKind): String {
        val i = p.protectedIdentities.indexOfFirst { it.id == source }; require(i >= 0)
        return when (kind) { PortKind.CHILD -> "C$i"; PortKind.LEFT -> "L$i"; PortKind.RIGHT -> "D$i"; else -> error("Invalid named port") }
    }

    /** Monotone hard repair bound plus exact expanded-size optimization, on the existing backend. */
    fun build(minimumKept: Int = 0): String = buildString {
        fun line(s: String) { append(s).append('\n') }
        fun atoms(base: String, names: List<String>) {
            if (names.isEmpty()) line("fact { no $base }") else line("one sig ${names.joinToString(", ")} extends $base {}")
        }
        line("abstract sig Unit {}")
        atoms("Unit", (0 until p.nodeBudget).map { "U$it" })
        line("abstract sig Label {}")
        atoms("Label", p.labels.indices.map { "T$it" })
        line("abstract sig Q {}")
        atoms("Q", context.registry.states.indices.map { "Q$it" })
        line("abstract sig Fiber { qi: one Q, qo: one Q }")
        atoms("Fiber", context.catalog.entries.map { "E${it.id}" })
        line("abstract sig Pos {}")
        atoms("Pos", (0 until positionCount).map { "P$it" })
        line("abstract sig Carrier { cost: set Unit }")
        line("abstract sig Anchor extends Carrier { lab: lone Label, state: lone Q }")
        atoms("Anchor", (0 until k).map { "A$it" })
        line("abstract sig Port extends Carrier { src: lone Anchor, target: lone Anchor, fiber: lone Fiber }")
        atoms("Port", portNames)
        line("one sig V { av: Anchor -> Pos, ev: Port -> Pos }")
        line("fun active: set Anchor { lab.Label }")
        line("fun used: set Port { target.Anchor }")
        line("fun lit: set Label { ${labelSet { it is MacroLabel.Literal }} }")
        line("fun un: set Label { ${labelSet { it is MacroLabel.Unary }} }")
        line("fun bin: set Label { ${labelSet { it is MacroLabel.Binary }} }")
        line("fun nonempty: set Fiber { ${union(context.catalog.entries.filter { it.key.nonEmpty }.map { "E${it.id}" })} }")
        line("fun graph: Anchor -> Anchor { ~src.target }")
        for ((fn, prefix) in listOf("child" to "C", "left" to "L", "right" to "D"))
            line("fun $fn[a: Anchor]: set Port { a.(${union((0 until k).map { "A$it->$prefix$it" })}) }")
        line("fact Structure {")
        line("no R.src\none R.target\none R.fiber")
        line("all a: Anchor | (some a.lab iff one a.state) and (some a.lab iff one a.cost)")
        line("all a: Anchor - active | no a.cost + a.state")
        line("all e: Port | (some e.target iff one e.fiber) and e.target in active")
        line("all e: Port - used | no e.cost")
        for (i in 0 until k) {
            line("C$i.src = A$i\nL$i.src = A$i\nD$i.src = A$i")
            line("(some C$i.target iff A$i.lab in un and some A$i.lab)")
            line("(some L$i.target iff A$i.lab in bin and some A$i.lab)")
            line("(some D$i.target iff A$i.lab in bin and some A$i.lab)")
        }
        line("no iden & ^graph")
        line("active = R.target.*graph")
        line("#(lab.bin) <= ${minOf(p.binaryBudget, k)}")
        if (p.uniqueLiteralIdentities) for ((i, label) in p.labels.withIndex())
            if (label is MacroLabel.Literal) line("lone lab.T$i")
        for ((i, protected) in p.protectedIdentities.withIndex()) {
            if (i >= k) line("no R.target") // Contradictory protected count is a supported UNSAT task.
            else line("A$i.lab = T${p.labels.indexOf(protected.label)}")
        }
        for (i in minOf(p.protectedIdentities.size, k) until k) {
            line("some A$i.lab and A$i.lab in un implies #(target.A$i) > 1")
            if (i > p.protectedIdentities.size) line("some A$i.lab implies some A${i-1}.lab")
        }
        line("all disj c, d: Carrier | no c.cost & d.cost")
        for (entry in context.catalog.entries) {
            line("E${entry.id}.qi = Q${entry.qIn}\nE${entry.id}.qo = Q${entry.qOut}")
        }
        for ((len, entries) in context.catalog.entries.groupBy { it.length })
            line("all e: used | e.fiber in (${union(entries.map { "E${it.id}" })}) implies #e.cost = $len")
        line("all e: used | e.fiber.qi = e.target.state")
        val accept = union(context.registry.states.indices.filter { p.automaton.isAccepting(context.registry.states[it]) }.map { "Q$it" })
        line("R.fiber.qo in ($accept)")
        for ((i, label) in p.labels.withIndex()) when (label) {
            is MacroLabel.Literal -> line("all a: active | a.lab = T$i implies a.state = Q${context.registry.literalTransition(label.proposition)}")
            is MacroLabel.Unary -> for (q in context.registry.states.indices)
                line("all a: active | a.lab = T$i and child[a].fiber.qo = Q$q implies a.state = Q${context.registry.unaryTransition(label.operator, q)}")
            is MacroLabel.Binary -> for (l in context.registry.states.indices) for (r in context.registry.states.indices)
                line("all a: active | a.lab = T$i and left[a].fiber.qo = Q$l and right[a].fiber.qo = Q$r implies a.state = Q${context.registry.binaryTransition(label.operator, l, r)}")
        }
        for (c in p.identityConstraints) when (c) {
            is MacroIdentityConstraint.LeftNotEqualRight -> line("all a: lab.bin | not (left[a].target = right[a].target and no (left[a].fiber + right[a].fiber) & nonempty)")
            is MacroIdentityConstraint.NoDAGReuse -> {
                val domain = if (c.excludeLiterals) "active - lab.lit" else "active"
                line("all a: $domain | lone ({e: used | e.target = a and e.fiber in nonempty})")
                line("all a: $domain | lone ({e: used - R | e.target = a and e.fiber not in nonempty}.src)")
                line("all a: $domain | (some e: used | e.target = a and e.fiber in nonempty) implies no {e: used - R | e.target = a and e.fiber not in nonempty}")
            }
            is MacroIdentityConstraint.NamedRoot -> if (p.protectedIdentities.size <= k) line("R.target = ${slot(c.target)} and R.fiber not in nonempty")
            is MacroIdentityConstraint.NamedDirectChild -> if (p.protectedIdentities.size <= k) line("${port(c.source,c.port)}.target = ${slot(c.target)} and ${port(c.source,c.port)}.fiber not in nonempty")
            is MacroIdentityConstraint.NamedReachability -> if (p.protectedIdentities.size <= k) line("${slot(c.target)} in ${slot(c.source)}.^graph")
        }
        line("}")
        line("fact Semantics {")
        line("V.av in active->Pos\nV.ev in used->Pos")
        for ((traceIndex, pos) in context.positions.withIndex()) {
            val offset = offsets[traceIndex]
            fun av(at: Int) = "(e.target->P${offset+at} in V.av)"
            fun ev(port: String, at: Int) = "($port->P${offset+at} in V.ev)"
            for ((type, entries) in context.catalog.entries.groupBy { it.key.semanticType }) {
                fun base(at: Int) = if (type.negated) "not ${av(at)}" else av(at)
                fun f(at: Int) = pos.future[at].joinToString(" or ", "(", ")") { base(it) }
                fun g(at: Int) = pos.future[at].joinToString(" and ", "(", ")") { base(it) }
                for (at in pos.successor.indices) {
                    val start = pos.succPow[type.xCount][at]
                    val rhs = when (type.tail) {
                        TemporalTail.ID -> base(start)
                        TemporalTail.F -> f(start)
                        TemporalTail.G -> g(start)
                        TemporalTail.FG -> pos.future[start].joinToString(" or ", "(", ")") { g(it) }
                        TemporalTail.GF -> pos.future[start].joinToString(" and ", "(", ")") { f(it) }
                    }
                    line("all e: used | e.fiber in (${union(entries.map { "E${it.id}" })}) implies (${ev("e",at)} iff ($rhs))")
                }
            }
            for ((i, label) in p.labels.withIndex()) for (at in pos.successor.indices) {
                val rhs = when (label) {
                    is MacroLabel.Literal -> if (pos.trace.getStateAt(at).values.getValue(label.proposition)) "some Unit" else "no Unit"
                    is MacroLabel.Unary -> when (label.operator) {
                        UnaryOperator.NOT -> "not ${ev("child[a]",at)}"
                        UnaryOperator.X -> ev("child[a]",pos.successor[at])
                        UnaryOperator.F -> pos.future[at].joinToString(" or ","(",")") { ev("child[a]",it) }
                        UnaryOperator.G -> pos.future[at].joinToString(" and ","(",")") { ev("child[a]",it) }
                    }
                    is MacroLabel.Binary -> when (label.operator) {
                        BinaryOperator.AND -> "${ev("left[a]",at)} and ${ev("right[a]",at)}"
                        BinaryOperator.OR -> "${ev("left[a]",at)} or ${ev("right[a]",at)}"
                        BinaryOperator.IMPLIES -> "${ev("left[a]",at)} implies ${ev("right[a]",at)}"
                        BinaryOperator.UNTIL -> error("U is unsupported")
                    }
                }
                line("all a: active | a.lab = T$i implies ((a->P${offset+at} in V.av) iff ($rhs))")
            }
            line("${if (traceIndex >= context.positives.size) "not " else ""}(R->P$offset in V.ev)")
        }
        line("}")
        val repair = p.objective as? MacroObjective.Repair
        val pairs = if (repair == null || p.protectedIdentities.size > k) emptyList() else repair.oldEdges.sortedWith(compareBy({it.source},{it.target})).map { "${slot(it.source)}->${slot(it.target)}" }
        line("fun kept: Anchor -> Anchor { (${if (pairs.isEmpty()) "none->none" else union(pairs)}) & ~src.( {e: used | e.fiber not in nonempty} <: target ) }")
        if (minimumKept > 0) line("fact { #kept >= $minimumKept }")
        line("fact Objective { minsome Carrier.cost }")
        // All counted domains have at most max(B,K,oldEdges) elements; no signed cardinality overflow.
        val maxCount = maxOf(p.nodeBudget, portNames.size, repair?.oldEdges?.size ?: 0)
        val bits = 2 + (31 - Integer.numberOfLeadingZeros(maxCount.coerceAtLeast(1)))
        line("run {} for $bits Int")
    }
}
