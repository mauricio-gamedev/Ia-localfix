package io.github.mauriciogamedev.ialocalfix

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LocalProposalRulesTest {
    @Test
    fun acceptsNormalRelativeProjectPaths() {
        assertTrue(LocalProposalRules.validatePath("app/src/main/AndroidManifest.xml"))
        assertTrue(LocalProposalRules.validatePath("README.md"))
        assertTrue(LocalProposalRules.validatePath(".gitignore"))
    }

    @Test
    fun rejectsTraversalAbsoluteAndSecretPaths() {
        assertFalse(LocalProposalRules.validatePath("../outside.txt"))
        assertFalse(LocalProposalRules.validatePath("/absolute.txt"))
        assertFalse(LocalProposalRules.validatePath("app\\outside.txt"))
        assertFalse(LocalProposalRules.validatePath(".env"))
        assertFalse(LocalProposalRules.validatePath("keys/id_rsa"))
        assertFalse(LocalProposalRules.validatePath("src/../outside.txt"))
    }
}
