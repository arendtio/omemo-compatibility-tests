package eu.siacs.conversations.crypto.axolotl;

import android.content.Context;

import androidx.test.core.app.ApplicationProvider;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.ConscryptMode;
import org.robolectric.annotation.Config;
import org.robolectric.util.ReflectionHelpers;
import org.whispersystems.libsignal.IdentityKeyPair;
import org.whispersystems.libsignal.SignalProtocolAddress;
import org.whispersystems.libsignal.SessionBuilder;
import org.whispersystems.libsignal.state.PreKeyRecord;

import android.os.Build;

import eu.siacs.conversations.AppSettings;
import eu.siacs.conversations.entities.Account;
import eu.siacs.conversations.persistance.DatabaseBackend;
import eu.siacs.conversations.services.XmppConnectionService;
import eu.siacs.conversations.xml.Element;
import eu.siacs.conversations.xml.WireXmlFixer;
import eu.siacs.conversations.xmpp.Jid;

/** Writes vendor-encrypted OMEMO XML for cross-client fixture tests. */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = Build.VERSION_CODES.P)
@ConscryptMode(ConscryptMode.Mode.OFF)
public class ConversationsNativeExportTest {

    @Test
    public void exportVendorEncryptedXml_fixture() throws Exception {
        Element wire = buildVendorEncryptedElement("slixmpp-cross-decrypt-body");
        String out = System.getenv("OMEMO_NATIVE_EXPORT_PATH");
        if (out != null && !out.isBlank()) {
            java.nio.file.Files.write(
                    java.nio.file.Path.of(out),
                    wire.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        }
        System.out.println("VENDOR_XML=" + wire.toString());
    }

    static Element buildVendorEncryptedElement(String body) throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        DatabaseBackend db = DatabaseBackend.getInstance(context);
        XmppConnectionService service = ReflectionHelpers.newInstance(XmppConnectionService.class);
        ReflectionHelpers.setField(service, "mBase", context);
        service.databaseBackend = db;
        ReflectionHelpers.setField(
                service,
                "appSettings",
                new AppSettings(context) {
                    @Override
                    public boolean isBTBVEnabled() {
                        return false;
                    }
                });

        Account alice = new Account(Jid.of("alice@localhost"), "alicepass");
        Account bob = new Account(Jid.of("bob@localhost"), "bobpass");
        db.createAccount(alice);
        db.createAccount(bob);

        SQLiteAxolotlStore aliceStore = new SQLiteAxolotlStore(alice, service);
        SQLiteAxolotlStore bobStore = new SQLiteAxolotlStore(bob, service);
        NativeTestHelper.seedDeviceKeys(bobStore);

        int aliceDevice = aliceStore.getLocalRegistrationId();
        SignalProtocolAddress bobAddress =
                new SignalProtocolAddress("bob@localhost", bobStore.getLocalRegistrationId());

        PreKeyRecord bobPreKey = bobStore.loadPreKey(1);
        IdentityKeyPair bobIdentity = bobStore.getIdentityKeyPair();
        new SessionBuilder(aliceStore, bobAddress)
                .process(NativeTestHelper.bundleForPeer(bobStore, bobPreKey));

        XmppAxolotlSession session =
                new XmppAxolotlSession(
                        alice,
                        aliceStore,
                        bobAddress,
                        bobIdentity.getPublicKey());
        NativeTestHelper.trustSession(aliceStore, session);

        XmppAxolotlMessage outbound =
                new XmppAxolotlMessage(alice.getJid().asBareJid(), aliceDevice);
        outbound.encrypt(body);
        outbound.addDevice(session);
        return WireXmlFixer.fixOmemoPayloadNamespace(outbound.toElement());
    }
}
