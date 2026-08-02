package eu.siacs.conversations.crypto.axolotl;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import android.content.Context;
import android.os.Build;

import androidx.test.core.app.ApplicationProvider;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.util.ReflectionHelpers;
import org.robolectric.annotation.ConscryptMode;
import org.robolectric.annotation.Config;
import org.whispersystems.libsignal.IdentityKeyPair;
import org.whispersystems.libsignal.SignalProtocolAddress;
import org.whispersystems.libsignal.SessionBuilder;
import org.whispersystems.libsignal.state.PreKeyRecord;

import eu.siacs.conversations.AppSettings;
import eu.siacs.conversations.entities.Account;
import eu.siacs.conversations.persistance.DatabaseBackend;
import eu.siacs.conversations.services.XmppConnectionService;
import eu.siacs.conversations.xml.WireXmlFixer;
import eu.siacs.conversations.xmpp.Jid;

/**
 * Two-party roundtrip using vendor {@link XmppAxolotlSession} + {@link SQLiteAxolotlStore}.
 */
@RunWith(RobolectricTestRunner.class)
@Config(sdk = Build.VERSION_CODES.P)
@ConscryptMode(ConscryptMode.Mode.OFF)
public class ConversationsAxolotlSessionNativeTest {

    private DatabaseBackend databaseBackend;
    private XmppConnectionService service;

    @Before
    public void setUp() {
        Context context = ApplicationProvider.getApplicationContext();
        databaseBackend = DatabaseBackend.getInstance(context);
        service = ReflectionHelpers.newInstance(XmppConnectionService.class);
        ReflectionHelpers.setField(service, "mBase", context);
        service.databaseBackend = databaseBackend;
        ReflectionHelpers.setField(
                service,
                "appSettings",
                new AppSettings(context) {
                    @Override
                    public boolean isBTBVEnabled() {
                        return false;
                    }
                });
    }

    @Test
    public void vendorSessionCipher_roundtrip_viaXmppAxolotlMessage() throws Exception {
        Account aliceAccount = new Account(Jid.of("alice@localhost"), "alicepass");
        Account bobAccount = new Account(Jid.of("bob@localhost"), "bobpass");
        databaseBackend.createAccount(aliceAccount);
        databaseBackend.createAccount(bobAccount);

        SQLiteAxolotlStore aliceStore = new SQLiteAxolotlStore(aliceAccount, service);
        SQLiteAxolotlStore bobStore = new SQLiteAxolotlStore(bobAccount, service);
        NativeTestHelper.seedDeviceKeys(bobStore);

        int aliceDeviceId = aliceStore.getLocalRegistrationId();
        int bobDeviceId = bobStore.getLocalRegistrationId();

        SignalProtocolAddress aliceAddress =
                new SignalProtocolAddress("alice@localhost", aliceDeviceId);
        SignalProtocolAddress bobAddress = new SignalProtocolAddress("bob@localhost", bobDeviceId);

        PreKeyRecord bobPreKey = bobStore.loadPreKey(1);
        IdentityKeyPair bobIdentity = bobStore.getIdentityKeyPair();
        new SessionBuilder(aliceStore, bobAddress)
                .process(NativeTestHelper.bundleForPeer(bobStore, bobPreKey));

        XmppAxolotlSession aliceToBobSession =
                new XmppAxolotlSession(
                        aliceAccount,
                        aliceStore,
                        bobAddress,
                        bobIdentity.getPublicKey());
        NativeTestHelper.trustSession(aliceStore, aliceToBobSession);

        XmppAxolotlMessage outbound =
                new XmppAxolotlMessage(aliceAccount.getJid().asBareJid(), aliceDeviceId);
        outbound.encrypt("vendor-session-roundtrip");
        outbound.addDevice(aliceToBobSession);

        XmppAxolotlSession bobFromAliceSession =
                new XmppAxolotlSession(
                        bobAccount,
                        bobStore,
                        aliceAddress,
                        aliceStore.getIdentityKeyPair().getPublicKey());

        XmppAxolotlMessage inbound =
                XmppAxolotlMessage.fromElement(
                        WireXmlFixer.fixOmemoPayloadNamespace(outbound.toElement()),
                        aliceAccount.getJid().asBareJid());
        var plaintext = inbound.decrypt(bobFromAliceSession, bobDeviceId);
        assertNotNull(plaintext);
        assertEquals("vendor-session-roundtrip", plaintext.getPlaintext());
    }
}
