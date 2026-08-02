package eu.siacs.conversations.wire;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import android.content.Context;

import androidx.test.core.app.ApplicationProvider;

import eu.siacs.conversations.crypto.axolotl.AxolotlService;
import eu.siacs.conversations.crypto.axolotl.NativeTestHelper;
import eu.siacs.conversations.crypto.axolotl.XmppAxolotlMessage;
import eu.siacs.conversations.entities.Account;
import eu.siacs.conversations.entities.Contact;
import eu.siacs.conversations.entities.Conversation;
import eu.siacs.conversations.entities.Message;
import eu.siacs.conversations.generator.MessageGenerator;
import eu.siacs.conversations.persistance.DatabaseBackend;
import eu.siacs.conversations.services.WireStubConnectionService;
import eu.siacs.conversations.xmpp.Jid;
import eu.siacs.conversations.xmpp.XmppConnection;
import eu.siacs.conversations.xmpp.manager.PepManager;
import eu.siacs.conversations.xmpp.manager.RosterManager;
import im.conversations.android.xmpp.model.axolotl.Encrypted;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.cert.X509Certificate;
import java.util.List;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;
import javax.net.ssl.HostnameVerifier;
import javax.net.ssl.X509TrustManager;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.jivesoftware.smack.SmackConfiguration;
import org.jivesoftware.smack.filter.StanzaFilter;
import org.jivesoftware.smack.packet.Stanza;
import org.jivesoftware.smack.roster.Roster;
import org.jivesoftware.smack.tcp.XMPPTCPConnection;
import org.jivesoftware.smack.tcp.XMPPTCPConnectionConfiguration;
import org.jxmpp.jid.EntityBareJid;
import org.jxmpp.jid.impl.JidCreate;
import org.robolectric.util.ReflectionHelpers;
import java.security.Security;

/**
 * Headless wire client: vendor {@link AxolotlService} crypto + Smack XMPP transport only.
 */
public final class NativeWireClient {

    private final Path dataDir;
    private final EntityBareJid jid;
    private final String password;
    private final String host;
    private final int port;

    private WireStubConnectionService wireService;
    private Account account;
    private AxolotlService axolotl;
    private XMPPTCPConnection connection;
    private final AtomicReference<String> lastBody = new AtomicReference<>();

    public NativeWireClient(
            Path dataDir,
            EntityBareJid jid,
            String password,
            String host,
            int port) {
        this.dataDir = dataDir;
        this.jid = jid;
        this.password = password;
        this.host = host;
        this.port = port;
    }

    public void connect() throws Exception {
        if (Security.getProvider(BouncyCastleProvider.PROVIDER_NAME) == null) {
            Security.addProvider(new BouncyCastleProvider());
        }
        Files.createDirectories(dataDir);
        Context context = ApplicationProvider.getApplicationContext();
        DatabaseBackend db = DatabaseBackend.getInstance(context);
        wireService = ReflectionHelpers.newInstance(WireStubConnectionService.class);
        wireService.attachContext(context);
        wireService.attachAppSettings(context);
        wireService.databaseBackend = db;

        String tlsMode = System.getenv("OMEMO_XMPP_SECURITY");
        boolean useTls;
        boolean autoTls;
        if (tlsMode == null || tlsMode.isBlank() || tlsMode.equalsIgnoreCase("auto")) {
            useTls = false;
            autoTls = true;
        } else if (tlsMode.equalsIgnoreCase("disabled")) {
            useTls = false;
            autoTls = false;
        } else {
            useTls = tlsMode.equalsIgnoreCase("required");
            autoTls = false;
        }

        var builder =
                XMPPTCPConnectionConfiguration.builder()
                        .setHost(host)
                        .setPort(port)
                        .setXmppDomain(jid.asDomainBareJid())
                        .setUsernameAndPassword(jid.getLocalpart(), password);

        if (useTls || autoTls) {
            X509TrustManager trustAll =
                    new X509TrustManager() {
                        @Override
                        public void checkClientTrusted(X509Certificate[] chain, String authType) {}

                        @Override
                        public void checkServerTrusted(X509Certificate[] chain, String authType) {}

                        @Override
                        public X509Certificate[] getAcceptedIssuers() {
                            return new X509Certificate[0];
                        }
                    };
            HostnameVerifier trustAllHosts = (hostname, session) -> true;
            builder
                    .setSecurityMode(
                            useTls
                                    ? XMPPTCPConnectionConfiguration.SecurityMode.required
                                    : XMPPTCPConnectionConfiguration.SecurityMode.ifpossible)
                    .setCustomX509TrustManager(trustAll)
                    .setHostnameVerifier(trustAllHosts);
        } else {
            builder.setSecurityMode(XMPPTCPConnectionConfiguration.SecurityMode.disabled);
        }

        SmackConfiguration.DEBUG = false;
        connection = new XMPPTCPConnection(builder.build());
        wireService.smackConnection = connection;

        connection.addAsyncStanzaListener(
                this::onSmackMessage,
                (StanzaFilter)
                        stanza -> stanza instanceof org.jivesoftware.smack.packet.Message);

        connection.connect();
        connection.login();
        Roster roster = Roster.getInstanceFor(connection);
        roster.setSubscriptionMode(Roster.SubscriptionMode.accept_all);
        connection.sendStanza(
                new org.jivesoftware.smack.packet.Presence(
                        org.jivesoftware.smack.packet.Presence.Type.available));

        account = new Account(Jid.of(jid.toString()), password);
        if (!db.getAccounts().stream().anyMatch(a -> a.getJid().asBareJid().equals(account.getJid().asBareJid()))) {
            db.createAccount(account);
        } else {
            account = db.getAccounts().stream()
                    .filter(a -> a.getJid().asBareJid().equals(account.getJid().asBareJid()))
                    .findFirst()
                    .orElse(account);
        }

        axolotl = new AxolotlService(account, wireService);
        XmppConnection xmppConnection = mock(XmppConnection.class);
        XmppConnection.Features features = mock(XmppConnection.Features.class);
        PepManager pepManager = mock(PepManager.class);
        RosterManager rosterManager = mock(RosterManager.class);
        when(pepManager.isAvailable()).thenReturn(true);
        when(features.pepPublishOptions()).thenReturn(true);
        when(xmppConnection.getFeatures()).thenReturn(features);
        when(xmppConnection.getManager(PepManager.class)).thenReturn(pepManager);
        when(xmppConnection.getManager(RosterManager.class)).thenReturn(rosterManager);
        when(xmppConnection.getAxolotlService()).thenReturn(axolotl);
        when(rosterManager.getContact(any(Jid.class)))
                .thenAnswer(
                        inv -> {
                            Contact contact = new Contact(inv.getArgument(0));
                            contact.setAccount(account);
                            return contact;
                        });
        account.setXmppConnection(xmppConnection);

        axolotl.onAdvancedStreamFeaturesAvailable(account);
        Thread.sleep(8000);
    }

    private void onSmackMessage(Stanza stanza) {
        try {
            im.conversations.android.xmpp.model.stanza.Message vendorMsg =
                    SmackXmlBridge.fromSmackStanza(
                            stanza, im.conversations.android.xmpp.model.stanza.Message.class);
            Encrypted encrypted = vendorMsg.getOnlyExtension(Encrypted.class);
            if (encrypted == null) {
                return;
            }
            Jid from = Jid.of(vendorMsg.getFrom().toString());
            XmppAxolotlMessage payload =
                    XmppAxolotlMessage.fromElement(encrypted, from.asBareJid());
            if (!payload.hasPayload()) {
                return;
            }
            XmppAxolotlMessage.XmppAxolotlPlaintextMessage plain =
                    axolotl.processReceivingPayloadMessage(payload, false);
            if (plain != null) {
                lastBody.set(plain.getPlaintext());
            }
        } catch (Exception ignored) {
            // skip non-OMEMO chat messages
        }
    }

    public void sendEncrypted(EntityBareJid peer, String body) throws Exception {
        Conversation conv =
                new Conversation(peer.getLocalpart().toString(), account, Jid.of(peer.toString()), Conversation.MODE_SINGLE);
        wireService.databaseBackend.createConversation(conv);
        preparePeer(peer, conv);
        Message message = new Message(conv, body, Message.ENCRYPTION_AXOLOTL);
        message.setCounterpart(Jid.of(peer.toString()));

        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(60);
        XmppAxolotlMessage encrypted = null;
        while (System.nanoTime() < deadline) {
            encrypted = axolotl.encrypt(message);
            if (encrypted != null) {
                break;
            }
            axolotl.fetchDeviceIds(Jid.of(peer.toString()));
            Thread.sleep(500);
        }
        if (encrypted == null) {
            throw new IllegalStateException("Vendor encrypt failed for peer " + peer);
        }
        MessageGenerator generator = new MessageGenerator(wireService);
        wireService.sendMessagePacket(
                account, generator.generateAxolotlChat(message, encrypted));
    }

    private void preparePeer(EntityBareJid peer, Conversation conv) throws Exception {
        Roster roster = Roster.getInstanceFor(connection);
        if (!roster.contains(peer)) {
            roster.createEntry(peer, peer.getLocalpart().toString(), null);
            Thread.sleep(1000);
        }
        Jid peerJid = Jid.of(peer.toString());
        axolotl.fetchDeviceIds(peerJid);
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(60);
        while (System.nanoTime() < deadline) {
            if (!axolotl.hasPendingKeyFetches(List.of(peerJid))) {
                break;
            }
            Thread.sleep(500);
            axolotl.fetchDeviceIds(peerJid);
        }
        if (axolotl.hasPendingKeyFetches(List.of(peerJid))) {
            throw new IllegalStateException("Timeout waiting for OMEMO device list for " + peer);
        }
        if (axolotl.isPepBroken()) {
            throw new IllegalStateException("Vendor PEP marked broken for " + peer);
        }
        if (axolotl.hasEmptyDeviceList(peerJid)) {
            throw new IllegalStateException("No OMEMO devices published for " + peer);
        }
        axolotl.createSessionsIfNeeded(conv);
        deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(60);
        while (System.nanoTime() < deadline) {
            if (!axolotl.hasPendingKeyFetches(List.of(peerJid))) {
                break;
            }
            Thread.sleep(500);
        }
        if (axolotl.hasPendingKeyFetches(List.of(peerJid))) {
            throw new IllegalStateException("Timeout waiting for OMEMO sessions with " + peer);
        }
        NativeTestHelper.trustPeerSessions(axolotl, account, peerJid);
    }

    public boolean awaitBody(String expected, long timeoutSeconds) throws InterruptedException {
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(timeoutSeconds);
        while (System.nanoTime() < deadline) {
            if (lastBody.get() != null && lastBody.get().equals(expected)) {
                return true;
            }
            Thread.sleep(250);
        }
        return lastBody.get() != null && lastBody.get().equals(expected);
    }

    public void disconnect() {
        if (connection != null && connection.isConnected()) {
            connection.disconnect();
        }
    }

    public static NativeWireClient fromArgs(String[] args) throws Exception {
        String jidStr = null;
        String password = null;
        String host = "127.0.0.1";
        int port = 5222;
        Path dataDir = Path.of("omemo-wire-data");
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--jid" -> jidStr = args[++i];
                case "--password" -> password = args[++i];
                case "--host" -> host = args[++i];
                case "--port" -> port = Integer.parseInt(args[++i]);
                case "--data-dir" -> dataDir = Path.of(args[++i]);
                default -> throw new IllegalArgumentException("Unknown arg: " + args[i]);
            }
        }
        if (jidStr == null || password == null) {
            throw new IllegalArgumentException("--jid and --password required");
        }
        return new NativeWireClient(
                dataDir, JidCreate.entityBareFrom(jidStr), password, host, port);
    }

    public static int runScenario(String[] args) {
        try {
            String mode = System.getProperty("wire.mode");
            String peerStr = System.getProperty("wire.peer");
            String sendBody = System.getProperty("wire.send");
            String expectBody = System.getProperty("wire.expect");

            NativeWireClient client = fromArgs(args);
            client.connect();

            System.out.println("RUNNER=conversations_android_crypto NATIVE=VENDOR_AXOLOTL");

            if ("send-wait".equals(mode)) {
                if (peerStr == null || sendBody == null || expectBody == null) {
                    throw new IllegalArgumentException("send-wait requires peer, send, expect");
                }
                EntityBareJid peer = JidCreate.entityBareFrom(peerStr);
                client.sendEncrypted(peer, sendBody);
                boolean ok = client.awaitBody(expectBody, 60);
                client.disconnect();
                if (!ok) {
                    System.err.println("TIMEOUT expected=" + expectBody + " got=" + client.lastBody.get());
                    return 1;
                }
                System.out.println("OK");
                return 0;
            }

            if ("send".equals(mode)) {
                if (peerStr == null || sendBody == null) {
                    throw new IllegalArgumentException("send requires peer and send");
                }
                client.sendEncrypted(JidCreate.entityBareFrom(peerStr), sendBody);
                Thread.sleep(1000);
                client.disconnect();
                System.out.println("OK");
                return 0;
            }

            if ("wait".equals(mode)) {
                if (expectBody == null) {
                    throw new IllegalArgumentException("wait requires expect");
                }
                boolean ok = client.awaitBody(expectBody, 90);
                client.disconnect();
                if (!ok) {
                    System.err.println("TIMEOUT expected=" + expectBody);
                    return 1;
                }
                System.out.println("OK");
                return 0;
            }

            throw new IllegalArgumentException("Unknown wire.mode=" + mode);
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace(System.err);
            return 1;
        }
    }
}
