package eu.siacs.conversations.crypto.axolotl;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.os.Build;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.ConscryptMode;
import org.robolectric.annotation.Config;

import eu.siacs.conversations.xml.Element;
import eu.siacs.conversations.xml.WireXmlFixer;

/** Vendor OMEMO XML must match legacy namespace wire contract. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = Build.VERSION_CODES.P)
@ConscryptMode(ConscryptMode.Mode.OFF)
public class ConversationsVendorXmlContractTest {

    @Test
    public void vendorEncryptedXml_usesLegacyNamespaceAndPayload() throws Exception {
        Element wire =
                WireXmlFixer.fixOmemoPayloadNamespace(
                        ConversationsNativeExportTest.buildVendorEncryptedElement("contract-body"));
        assertEquals("encrypted", wire.getName());
        assertEquals(AxolotlService.PEP_PREFIX, wire.getNamespace());
        assertNotNull(wire.findChild("header"));
        assertNotNull(wire.findChild("payload", AxolotlService.PEP_PREFIX));
        assertTrue(wire.findChild("header").findChild("iv") != null);
    }
}
