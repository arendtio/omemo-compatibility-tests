package eu.siacs.conversations.services;

import android.content.Context;

import java.util.function.Consumer;

import eu.siacs.conversations.AppSettings;
import eu.siacs.conversations.entities.Account;
import eu.siacs.conversations.generator.IqGenerator;
import eu.siacs.conversations.wire.SmackXmlBridge;
import im.conversations.android.xmpp.model.stanza.Iq;
import im.conversations.android.xmpp.model.stanza.Message;
import org.jivesoftware.smack.SmackException;
import org.jivesoftware.smack.packet.Stanza;
import org.jivesoftware.smack.tcp.XMPPTCPConnection;

/** Minimal {@link XmppConnectionService} for headless native wire (Smack transport only). */
public class WireStubConnectionService extends XmppConnectionService {

    public XMPPTCPConnection smackConnection;

    public void attachContext(Context context) {
        org.robolectric.util.ReflectionHelpers.setField(this, "mBase", context);
    }

  public void attachAppSettings(Context context) {
        org.robolectric.util.ReflectionHelpers.setField(
                this,
                "appSettings",
                new AppSettings(context) {
                    @Override
                    public boolean isBTBVEnabled() {
                        return false;
                    }
                });
    }

    @Override
    public void sendMessagePacket(
            Account account, im.conversations.android.xmpp.model.stanza.Message packet) {
        if (smackConnection == null) {
            throw new IllegalStateException("smackConnection not set");
        }
        try {
            Stanza stanza = SmackXmlBridge.toSmackStanza(packet);
            smackConnection.sendStanza(stanza);
        } catch (Exception e) {
            throw new IllegalStateException("Failed to send vendor message via Smack", e);
        }
    }

    @Override
    public void sendIqPacket(final Account account, final Iq packet, final Consumer<Iq> callback) {
        if (smackConnection == null) {
            throw new IllegalStateException("smackConnection not set");
        }
        try {
            Stanza request = SmackXmlBridge.toSmackStanza(packet);
            if (request instanceof org.jivesoftware.smack.packet.IQ iqRequest) {
                Stanza response =
                        smackConnection.createStanzaCollectorAndSend(iqRequest).nextResultOrThrow();
                Iq vendorResponse = SmackXmlBridge.fromSmackStanza(response, Iq.class);
                if (callback != null) {
                    callback.accept(vendorResponse);
                }
                return;
            }
            throw new IllegalStateException("Expected IQ stanza for sendIqPacket");
        } catch (SmackException.NotConnectedException
                | SmackException.NotLoggedInException
                | org.jivesoftware.smack.SmackException.NoResponseException
                | org.jivesoftware.smack.SmackException.SecurityRequiredException
                | InterruptedException e) {
            if (callback != null) {
                callback.accept(Iq.TIMEOUT);
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed IQ exchange via Smack", e);
        }
    }

    @Override
    public IqGenerator getIqGenerator() {
        return new IqGenerator(this);
    }
}
