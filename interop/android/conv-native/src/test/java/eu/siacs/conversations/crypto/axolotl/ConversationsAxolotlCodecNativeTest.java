package eu.siacs.conversations.crypto.axolotl;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import android.os.Build;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.annotation.Config;

import eu.siacs.conversations.xml.Element;
import eu.siacs.conversations.xmpp.Jid;

import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.ConscryptMode;

/** Proves vendor {@link XmppAxolotlMessage} AES-GCM + axolotl XML (not Smack proxy). */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = Build.VERSION_CODES.P)
@ConscryptMode(ConscryptMode.Mode.OFF)
public class ConversationsAxolotlCodecNativeTest {

    @Test
    public void vendorXmppAxolotlMessage_encrypt_roundtrip() throws CryptoFailedException {
        Jid from = Jid.of("alice@localhost");
        XmppAxolotlMessage message = new XmppAxolotlMessage(from, 424242);
        message.encrypt("conversations-native-codec");
        Element encrypted = message.toElement();
        assertEquals("encrypted", encrypted.getName());
        assertEquals("eu.siacs.conversations.axolotl", encrypted.getNamespace());
        assertNotNull(encrypted.findChild("header"));
        assertNotNull(encrypted.findChild("payload"));
        assertTrue(encrypted.findChild("header").findChild("iv") != null);
    }
}
