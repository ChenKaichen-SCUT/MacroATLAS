package cmu.s3d.ltl.macro.search

import cmu.s3d.ltl.samples2ltl.Task
import cmu.s3d.ltl.macro.constraint.*
import cmu.s3d.ltl.macro.dag.NodeId
import cmu.s3d.ltl.macro.kernel.PortKind
import cmu.s3d.ltl.macro.unary.UnaryOperator

/** Whole-block canonical recognition. Unknown characters, declarations and leftover clauses fail closed.
 * TaskParser exposes raw text, not an Alloy AST. We intentionally do not implement general Alloy.
 */
object RecognizedConstraintAnalyzer {
    private fun tokens(s: String): String {
        val clean = s.replace(Regex("/\\*[\\s\\S]*?\\*/|//[^\\n]*|--[^\\n]*"), " ")
        val token = Regex("[A-Za-z_][A-Za-z_0-9]*|[0-9]+|->|[{}()\\[\\].:*+&|=~,-]")
        var end = 0
        val out = arrayListOf<String>()
        for (m in token.findAll(clean)) {
            require(clean.substring(end, m.range.first).isBlank())
            out.add(m.value); end = m.range.last + 1
        }
        require(clean.substring(end).isBlank())
        return out.joinToString(" ")
    }

    // Public canonical forms are also used by the real TaskParser fixtures and documentation.
    val PROPOSITIONAL = "all n: DAGNode | n in (Literal + Neg + And + Or + Imply)"
    val NNF = "all n: Neg | n.l in Literal"
    val CNF = "all n: DAGNode | n in (Literal + Neg + And + Or)\nall n: Neg | n.l in Literal\nall n: Or | no childrenOf[n] & And"
    val DNF = "all n: DAGNode | n in (Literal + Neg + And + Or)\nall n: Neg | n.l in Literal\nall n: And | no childrenOf[n] & Or"
    val GLOBAL_PROP = "root in G\nall n: childrenAndSelfOf[root.l] | n in (Literal + Neg + And + Or + Imply)"
    val RESPONSE = "root in G\nroot.l in Imply\nroot.l.r in F\nall n: childrenAndSelfOf[root.l.l] + childrenAndSelfOf[root.l.r.l] | n in (Literal + Neg + And + Or + Imply)"

    private val NO_SHARED_LITERAL_BRANCH =
        "all n: root.*(l+r) | (n.l.*(l+r) & n.r.*(l+r) & Literal) = none"
    private fun peterson(vararg clauses: String) = tokens("fact { ${clauses.joinToString(" ")} $NO_SHARED_LITERAL_BRANCH }")
    private val PETERSON = mapOf(
        peterson("root in G", "x2 in root.*(l+r)", "x8 in root.*(l+r)") to Pair(false, listOf("x2", "x8")),
        peterson("root in G", "root.l in Imply", "root.l.r in F", "x6 in root.*(l+r)") to Pair(true, listOf("x6")),
        peterson("root in G", "root.l in Imply", "root.l.r in F", "x6 in root.*(l+r)", "x2 in root.*(l+r)") to Pair(true, listOf("x6", "x2"))
    )
    private val VOTING = mapOf(
        tokens("fact { root in G }") to false,
        tokens("fact { root in G all n: Neg | n.l in Literal }") to true
    )
    private val ROBOT_RA = tokens("""
        one sig And0 extends And {} one sig F0 extends F {} one sig G0 extends G {} one sig Neg0 extends Neg {}
        fact { maxsome[2] subDAG[root] & (And0->G0 + G0->Neg0 + Neg0->x2 + And0->F0 + F0->x0)
        all n: DAGNode - Literal | lone n.~(l+r) no l & r root in And }
    """.trimIndent())
    private val ROBOT_RR = tokens("""
        one sig F0 extends F {} one sig F1 extends F {} one sig And0 extends And {}
        fact { maxsome[2] subDAG[root] & (And0->F0 + F0->x0 + And0->F1 + F1->x1)
        all n: DAGNode - Literal | lone n.~(l+r) no l & r root in And all n: Neg | n.l in Literal }
    """.trimIndent())
    private val WEAKEN_ANTECEDENT = tokens("""
        fact { root = G0 all imply: Imply {
          all n: childrenOf[imply] | n in (Literal + And + Or + Neg)
          all n: childrenOf[imply] & Neg | n.l in Literal
          all n: childrenAndSelfOf[imply.l] & Or | no childrenOf[n] & And
          all n: childrenAndSelfOf[imply.r] & And | no childrenOf[n] & Or
        } }
        one sig G0 extends G {} { l = Imply0 }
        one sig Imply0 extends Imply {}
        fact {
          Imply0.l = x0 or (Imply0.l in And and Imply0.l.l = x0)
          Imply0.r = x1 or (Imply0.r in Or and Imply0.r.l = x1)
        }
    """.trimIndent())
    private val WEAKEN_CONSEQUENT = tokens("""
        fact { root = G0 all imply: Imply {
          all n: childrenOf[imply] | n in (Literal + And + Or + Neg)
          all n: childrenOf[imply] & Neg | n.l in Literal
          all n: childrenAndSelfOf[imply.l] & Or | no childrenOf[n] & And
          all n: childrenAndSelfOf[imply.r] & And | no childrenOf[n] & Or
        } }
        one sig G0 extends G {} { l = Imply0 }
        one sig Imply0 extends Imply {}
        one sig And0 extends And {}
        fact {
          Imply0.l = x0 or (Imply0.l in And and Imply0.l.l = x0)
          Imply0.r = And0 or (Imply0.r in Or and Imply0.r.l = And0)
          (And0->x1 + And0->x2) in subDAG[Imply0.r]
        }
    """.trimIndent())

    fun analyze(task: Task, binaryBudget: Int?, nodeBudget: Int = task.maxNumOfOP + task.literals.size,
                minimumSize: Boolean = true): MacroTaskAnalysis {
        fun unsupported(reason: MacroUnsupportedReason, detail: String) = MacroTaskAnalysis.Unsupported(listOf(reason), detail)
        if ("Until" !in task.excludedOperators) return unsupported(MacroUnsupportedReason.BINARY_TEMPORAL_UNTIL_REQUIRED, "The candidate alphabet includes U")
        if (binaryBudget == null) return unsupported(MacroUnsupportedReason.BINARY_BUDGET_MISSING, "Specify --macro-max-binary")
        if (nodeBudget < 1 || binaryBudget < 0) return unsupported(MacroUnsupportedReason.INVALID_BUDGET, "Require B >= 1 and b >= 0")
        if (!minimumSize) return unsupported(MacroUnsupportedReason.UNSUPPORTED_OBJECTIVE, "Only minimum size and recognized repair are supported")
        if ((task.positiveExamples + task.negativeExamples).any { it.length() == 0 })
            return unsupported(MacroUnsupportedReason.INVALID_TRACE, "Every trace must be nonempty")
        val profiles = arrayListOf<ConstraintAutomaton<*>>()
        val identities = linkedMapOf<String, MacroLabel>()
        val identity = arrayListOf<MacroIdentityConstraint>()
        val reachable = hashSetOf<String>()
        val features = arrayListOf<String>()
        val oldEdges = linkedSetOf<ProtectedEdge>()
        var repair = false
        val unary = UnaryOperator.LEXICAL_ORDER.filter { it.atlasName !in task.excludedOperators }
        val binary = BinaryOperator.values().filter { it != BinaryOperator.UNTIL && it.atlasName !in task.excludedOperators }
        fun <Q : Any> minimized(automaton: ConstraintAutomaton<Q>) =
            MinimizedConstraintAutomaton(automaton, task.literals, unary, binary)
        fun label(name: String): MacroLabel? = when {
            name in task.literals -> MacroLabel.Literal(name)
            unary.any { it.atlasName == name } -> MacroLabel.Unary(unary.single { it.atlasName == name })
            binary.any { it.atlasName == name } -> MacroLabel.Binary(binary.single { it.atlasName == name })
            else -> null
        }
        fun protect(name: String): NodeId {
            if (name in task.literals) identities.putIfAbsent(name, MacroLabel.Literal(name))
            require(name in identities)
            return NodeId(name)
        }
        try {
            val text = tokens(task.customConstraints ?: "")

            // The paper artifact contains four constrained benchmark families with a
            // small, fixed grammar.  Recognize their complete blocks before the generic
            // clause grammar, and compile each to an exact finite-state/identity plan.
            PETERSON[text]?.takeIf { (response, _) ->
                "G" !in task.excludedOperators && (!response || listOf("Imply", "F").none { it in task.excludedOperators })
            }?.let { (response, required) ->
                val automata = arrayListOf<ConstraintAutomaton<*>>(RootOperatorAutomaton("G"))
                if (response) automata.add(ResponseOuterShapeAutomaton())
                required.forEach { automata.add(RequiredPropositionAutomaton(it)) }
                val plan = MacroConstraintPlan(minimized(ProductConstraintAutomaton(automata)), task.literals, nodeBudget, binaryBudget,
                    unary, binary, identityConstraints = listOf(MacroIdentityConstraint.NoSharedLiteralBranches),
                    uniqueLiteralIdentities = true, requiredRootUnary = UnaryOperator.G)
                return MacroTaskAnalysis.Supported(plan, listOf("OfficialPeterson", "NoSharedLiteralBranches") +
                    required.map { "RequiredProposition($it)" })
            }
            VOTING[text]?.takeIf { "G" !in task.excludedOperators }?.let { nnf ->
                val automata = arrayListOf<ConstraintAutomaton<*>>(RootOperatorAutomaton("G"))
                if (nnf) automata.add(NnfAutomaton())
                val plan = MacroConstraintPlan(minimized(ProductConstraintAutomaton(automata)), task.literals, nodeBudget, binaryBudget,
                    unary, binary, uniqueLiteralIdentities = true, requiredRootUnary = UnaryOperator.G)
                return MacroTaskAnalysis.Supported(plan, listOf("OfficialVoting") + if (nnf) listOf("NNF") else emptyList())
            }
            if (text == WEAKEN_ANTECEDENT || text == WEAKEN_CONSEQUENT) {
                val consequent = text == WEAKEN_CONSEQUENT
                val automaton = minimized(WeakeningTemplateAutomaton(consequent))
                val plan = MacroConstraintPlan(automaton,
                    task.literals, nodeBudget, binaryBudget, unary, binary, uniqueLiteralIdentities = true,
                    requiredRootUnary = UnaryOperator.G)
                return MacroTaskAnalysis.Supported(plan, listOf(if (consequent) "OfficialWeakeningConsequent" else "OfficialWeakeningAntecedent"))
            }
            if (text == ROBOT_RA || text == ROBOT_RR) {
                fun protected(name: String, label: MacroLabel) = ProtectedIdentity(NodeId(name), label)
                val ra = text == ROBOT_RA
                val declared = if (ra) listOf(
                    protected("And0", MacroLabel.Binary(BinaryOperator.AND)),
                    protected("F0", MacroLabel.Unary(UnaryOperator.F)),
                    protected("G0", MacroLabel.Unary(UnaryOperator.G)),
                    protected("Neg0", MacroLabel.Unary(UnaryOperator.NOT)),
                    protected("x0", MacroLabel.Literal("x0")), protected("x2", MacroLabel.Literal("x2"))
                ) else listOf(
                    protected("And0", MacroLabel.Binary(BinaryOperator.AND)),
                    protected("F0", MacroLabel.Unary(UnaryOperator.F)),
                    protected("F1", MacroLabel.Unary(UnaryOperator.F)),
                    protected("x0", MacroLabel.Literal("x0")), protected("x1", MacroLabel.Literal("x1"))
                )
                val edgeNames = if (ra) listOf("And0" to "G0", "G0" to "Neg0", "Neg0" to "x2", "And0" to "F0", "F0" to "x0")
                    else listOf("And0" to "F0", "F0" to "x0", "And0" to "F1", "F1" to "x1")
                val automata = arrayListOf<ConstraintAutomaton<*>>(RootOperatorAutomaton("And"))
                if (!ra) automata.add(NnfAutomaton())
                val plan = MacroConstraintPlan(minimized(ProductConstraintAutomaton(automata)), task.literals, nodeBudget, binaryBudget,
                    unary, binary, declared, listOf(MacroIdentityConstraint.NoDAGReuse(true), MacroIdentityConstraint.LeftNotEqualRight),
                    MacroObjective.Repair(edgeNames.map { ProtectedEdge(NodeId(it.first), NodeId(it.second)) }),
                    uniqueLiteralIdentities = true, requiredProtectedIdentities = emptyList())
                return MacroTaskAnalysis.Supported(plan, listOf(if (ra) "OfficialRobotRA" else "OfficialRobotRR", "Repair", "NoDAGReuse", "LeftNotEqualRight"))
            }

            val block = Regex("one sig ([A-Za-z_][A-Za-z_0-9]*) extends ([A-Za-z_][A-Za-z_0-9]*) \\{ \\}|fact \\{ ([^{}]*)\\}")
            val matches = block.findAll(text).toList()
            var end = 0
            for (m in matches) {
                require(text.substring(end, m.range.first).isBlank())
                end = m.range.last + 1
                if (m.groupValues[1].isNotEmpty()) {
                    val name = m.groupValues[1]
                    require(Regex("(?:Neg|X|F|G|And|Or|Imply)[0-9]+").matches(name))
                    require(name !in identities && name !in task.literals)
                    identities[name] = requireNotNull(label(m.groupValues[2]))
                }
            }
            require(text.substring(end).isBlank())
            for (m in matches.filter { it.groupValues[1].isEmpty() }) {
                val body = m.groupValues[3].trim()
                // LTLLearner omits excluded operator signatures entirely. A reference to one
                // is invalid Alloy, not an understood constraint that we may reinterpret.
                val operatorNames = UnaryOperator.LEXICAL_ORDER.map { it.atlasName } + BinaryOperator.values().map { it.atlasName }
                require(body.split(' ').none { it in operatorNames && it in task.excludedOperators })
                when (body) {
                    tokens(PROPOSITIONAL) -> { profiles.add(PropositionalAutomaton()); features.add("PropositionalOnly") }
                    tokens(NNF) -> { profiles.add(NnfAutomaton()); features.add("NNF") }
                    tokens(CNF) -> { profiles.add(CnfAutomaton()); features.add("CNF") }
                    tokens(DNF) -> { profiles.add(DnfAutomaton()); features.add("DNF") }
                    tokens(GLOBAL_PROP) -> { profiles.add(FixedTemplateAutomaton()); features.add("G(Prop)") }
                    tokens(RESPONSE) -> { profiles.add(FixedTemplateAutomaton(true)); features.add("G(Prop -> F Prop)") }
                    tokens("all n: DAGNode | lone n.~(l+r)") -> identity.add(MacroIdentityConstraint.NoDAGReuse())
                    tokens("all n: DAGNode - Literal | lone n.~(l+r)") -> identity.add(MacroIdentityConstraint.NoDAGReuse(true))
                    tokens("no l & r") -> identity.add(MacroIdentityConstraint.LeftNotEqualRight)
                    else -> {
                        val required = Regex("(x[0-9]+) in childrenAndSelfOf \\[ root \\]").matchEntire(body)
                        val rootKind = Regex("root in (Neg|X|F|G|And|Or|Imply)").matchEntire(body)
                        val direct = Regex("([A-Za-z_][A-Za-z_0-9]*) \\. (l|r) = ([A-Za-z_][A-Za-z_0-9]*)").matchEntire(body)
                        val reach = Regex("([A-Za-z_][A-Za-z_0-9]*) in childrenOf \\[ ([A-Za-z_][A-Za-z_0-9]*) \\]").matchEntire(body)
                        val keepReach = Regex("([A-Za-z_][A-Za-z_0-9]*) in childrenAndSelfOf \\[ root \\]").matchEntire(body)
                        val root = Regex("root = ([A-Za-z_][A-Za-z_0-9]*)").matchEntire(body)
                        val repairBody = Regex("maxsome \\[ 2 \\] subDAG \\[ root \\] & \\( (.*) \\)").matchEntire(body)
                        when {
                            required != null -> {
                                val p = required.groupValues[1]; require(p in task.literals)
                                profiles.add(RequiredPropositionAutomaton(p)); features.add("RequiredProposition($p)")
                                // If the literal is referenced by identity elsewhere, this also proves its reachability.
                                reachable.add(p)
                            }
                            rootKind != null -> profiles.add(RootOperatorAutomaton(rootKind.groupValues[1]))
                            direct != null -> {
                                val src = protect(direct.groupValues[1]); val dst = protect(direct.groupValues[3])
                                val port = if (direct.groupValues[2] == "r") PortKind.RIGHT
                                    else if (identities[src.value] is MacroLabel.Unary) PortKind.CHILD else PortKind.LEFT
                                identity.add(MacroIdentityConstraint.NamedDirectChild(src, port, dst))
                            }
                            reach != null -> identity.add(MacroIdentityConstraint.NamedReachability(protect(reach.groupValues[2]), protect(reach.groupValues[1])))
                            keepReach != null -> { protect(keepReach.groupValues[1]); reachable.add(keepReach.groupValues[1]) }
                            root != null -> { identity.add(MacroIdentityConstraint.NamedRoot(protect(root.groupValues[1]))); reachable.add(root.groupValues[1]) }
                            repairBody != null -> {
                                require(!repair); repair = true
                                for (pair in repairBody.groupValues[1].split(" + ")) {
                                    val edge = requireNotNull(Regex("([A-Za-z_][A-Za-z_0-9]*) -> ([A-Za-z_][A-Za-z_0-9]*)").matchEntire(pair))
                                    oldEdges.add(ProtectedEdge(protect(edge.groupValues[1]), protect(edge.groupValues[2])))
                                }
                            }
                            else -> return unsupported(MacroUnsupportedReason.UNKNOWN_CUSTOM_ALLOY_CONSTRAINT, "Unrecognized complete fact: $body")
                        }
                    }
                }
            }
            // Reachability may be proved transitively by hard named edges/reachability, never by the soft repair objective.
            do {
                val size = reachable.size
                identity.forEach { c -> when (c) {
                    is MacroIdentityConstraint.NamedDirectChild -> if (c.source.value in reachable) reachable.add(c.target.value)
                    is MacroIdentityConstraint.NamedReachability -> if (c.source.value in reachable) reachable.add(c.target.value)
                    else -> Unit
                } }
            } while (size != reachable.size)
            if (!reachable.containsAll(identities.keys)) return unsupported(MacroUnsupportedReason.PROTECTED_IDENTITY_NOT_RESOLVABLE,
                "Named nodes must be required reachable by hard constraints; soft oldSpec edges do not imply this")
            val plan = MacroConstraintPlan(minimized(ProductConstraintAutomaton(profiles)), task.literals, nodeBudget, binaryBudget,
                unary, binary, identities.map { ProtectedIdentity(NodeId(it.key), it.value) }, identity,
                if (repair) MacroObjective.Repair(oldEdges) else MacroObjective.MinExpandedSize, uniqueLiteralIdentities = true)
            return MacroTaskAnalysis.Supported(plan, features + identity.map { it.javaClass.simpleName } + if (repair) listOf("Repair") else emptyList())
        } catch (e: IllegalArgumentException) {
            return unsupported(MacroUnsupportedReason.UNKNOWN_CUSTOM_ALLOY_CONSTRAINT, "Outside the canonical constraint grammar: ${e.message}")
        }
    }
}
