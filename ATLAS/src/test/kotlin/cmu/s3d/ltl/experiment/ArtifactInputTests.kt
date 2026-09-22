package cmu.s3d.ltl.experiment

import cmu.s3d.ltl.samples2ltl.TaskParser
import java.io.File
import org.junit.jupiter.api.Test
import kotlin.test.*

class ArtifactInputTests {
    @Test fun incompleteOfficialVotingInputIsNotAConcreteVerificationFailure() {
        val file = File("benchmark/voting_machine/voting5.trace")
        val original = file.readText()
        val error = assertFailsWith<InvalidArtifactTraceException> {
            ArtifactVerifier.requireConcreteInput(TaskParser.parseTask(original))
        }
        assertTrue(error.message!!.contains("expected 10 propositions, got 6"))
        assertEquals(original, file.readText())
    }

    @Test fun concreteInputsAndOriginalFiniteTraceConventionRemainAccepted() {
        for (name in listOf("literal", "next", "eventually", "nnf", "repair")) {
            ArtifactVerifier.requireConcreteInput(TaskParser.parseTask(File("src/test/resources/macro/$name.trace").readText()))
        }
        val finite = "1,0;0,1\n---\n0,0\n---\nG,F,!,U,&,|,->,X\n---\n2\n"
        ArtifactVerifier.requireConcreteInput(TaskParser.parseTask(finite))
    }
}
