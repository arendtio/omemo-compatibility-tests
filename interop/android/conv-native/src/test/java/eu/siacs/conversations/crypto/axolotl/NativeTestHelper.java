package eu.siacs.conversations.crypto.axolotl;

import eu.siacs.conversations.entities.Account;
import eu.siacs.conversations.entities.Contact;
import eu.siacs.conversations.xmpp.Jid;
import org.whispersystems.libsignal.IdentityKeyPair;
import org.whispersystems.libsignal.InvalidKeyIdException;
import org.whispersystems.libsignal.state.PreKeyBundle;
import org.whispersystems.libsignal.state.PreKeyRecord;
import org.whispersystems.libsignal.state.SignedPreKeyRecord;
import org.whispersystems.libsignal.util.KeyHelper;

import java.util.List;

/** Seeds vendor {@link SQLiteAxolotlStore} like {@code AxolotlService} publish path. */
public final class NativeTestHelper {

    private NativeTestHelper() {}

    static void seedDeviceKeys(SQLiteAxolotlStore store) throws Exception {
        IdentityKeyPair identity = store.getIdentityKeyPair();
        SignedPreKeyRecord signed = KeyHelper.generateSignedPreKey(identity, 1);
        store.storeSignedPreKey(signed.getId(), signed);
        List<PreKeyRecord> preKeys = KeyHelper.generatePreKeys(1, 10);
        for (PreKeyRecord record : preKeys) {
            store.storePreKey(record.getId(), record);
        }
    }

    static PreKeyBundle bundleForPeer(SQLiteAxolotlStore store, PreKeyRecord preKey)
            throws InvalidKeyIdException {
        SignedPreKeyRecord signed = store.loadSignedPreKey(1);
        IdentityKeyPair identity = store.getIdentityKeyPair();
        return new PreKeyBundle(
                0,
                store.getLocalRegistrationId(),
                preKey.getId(),
                preKey.getKeyPair().getPublicKey(),
                signed.getId(),
                signed.getKeyPair().getPublicKey(),
                signed.getSignature(),
                identity.getPublicKey());
    }

    static void trustSession(SQLiteAxolotlStore store, XmppAxolotlSession session) {
        store.setFingerprintStatus(
                session.getFingerprint(), FingerprintStatus.createActiveTrusted());
        session.setTrust(FingerprintStatus.createActiveTrusted());
    }

    public static void trustPeerSessions(AxolotlService axolotl, Account account, Jid peer) {
        Contact contact = new Contact(peer);
        contact.setAccount(account);
        for (XmppAxolotlSession session : axolotl.findSessionsForContact(contact)) {
            session.setTrust(FingerprintStatus.createActiveTrusted());
        }
    }
}
