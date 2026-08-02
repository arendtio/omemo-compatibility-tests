package eu.siacs.conversations.crypto.axolotl;

import android.content.Context;

import androidx.test.core.app.ApplicationProvider;

import org.robolectric.util.ReflectionHelpers;
import org.whispersystems.libsignal.IdentityKeyPair;
import org.whispersystems.libsignal.SignalProtocolAddress;
import org.whispersystems.libsignal.SessionBuilder;
import org.whispersystems.libsignal.state.PreKeyRecord;

import eu.siacs.conversations.AppSettings;
import eu.siacs.conversations.entities.Account;
import eu.siacs.conversations.persistance.DatabaseBackend;
import eu.siacs.conversations.services.XmppConnectionService;
import eu.siacs.conversations.xml.Element;
import eu.siacs.conversations.xml.WireXmlFixer;
import eu.siacs.conversations.xmpp.Jid;

/** Vendor axolotl roundtrip helpers (no Smack). */
final class ConversationsNativeRoundtrip {

    private ConversationsNativeRoundtrip() {}

    static String roundtrip(String body) throws Exception {
        Context context = ApplicationProvider.getApplicationContext();
        DatabaseBackend db = DatabaseBackend.getInstance(context);
        XmppConnectionService service = newService(context, db);

        Account alice = new Account(Jid.of("alice@localhost"), "alicepass");
        Account bob = new Account(Jid.of("bob@localhost"), "bobpass");
        db.createAccount(alice);
        db.createAccount(bob);

        SQLiteAxolotlStore aliceStore = new SQLiteAxolotlStore(alice, service);
        SQLiteAxolotlStore bobStore = new SQLiteAxolotlStore(bob, service);
        NativeTestHelper.seedDeviceKeys(bobStore);

        int aliceDevice = aliceStore.getLocalRegistrationId();
        int bobDevice = bobStore.getLocalRegistrationId();
        SignalProtocolAddress aliceAddress =
                new SignalProtocolAddress("alice@localhost", aliceDevice);
        SignalProtocolAddress bobAddress =
                new SignalProtocolAddress("bob@localhost", bobDevice);

        PreKeyRecord bobPreKey = bobStore.loadPreKey(1);
        IdentityKeyPair bobIdentity = bobStore.getIdentityKeyPair();
        new SessionBuilder(aliceStore, bobAddress)
                .process(NativeTestHelper.bundleForPeer(bobStore, bobPreKey));

        XmppAxolotlSession aliceToBob =
                new XmppAxolotlSession(
                        alice, aliceStore, bobAddress, bobIdentity.getPublicKey());
        NativeTestHelper.trustSession(aliceStore, aliceToBob);

        XmppAxolotlMessage outbound = new XmppAxolotlMessage(alice.getJid().asBareJid(), aliceDevice);
        outbound.encrypt(body);
        outbound.addDevice(aliceToBob);

        XmppAxolotlSession bobFromAlice =
                new XmppAxolotlSession(
                        bob,
                        bobStore,
                        aliceAddress,
                        aliceStore.getIdentityKeyPair().getPublicKey());

        XmppAxolotlMessage inbound =
                XmppAxolotlMessage.fromElement(
                        WireXmlFixer.fixOmemoPayloadNamespace(outbound.toElement()),
                        alice.getJid().asBareJid());
        return inbound.decrypt(bobFromAlice, bobDevice).getPlaintext();
    }

    static Element exportVendorXml(String body) throws Exception {
        return ConversationsNativeExportTest.buildVendorEncryptedElement(body);
    }

    private static XmppConnectionService newService(Context context, DatabaseBackend db) {
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
        return service;
    }
}
