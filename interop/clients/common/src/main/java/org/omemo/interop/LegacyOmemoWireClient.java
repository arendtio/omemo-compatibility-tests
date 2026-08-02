package org.omemo.interop;

import org.jivesoftware.smack.SmackConfiguration;
import org.jivesoftware.smack.packet.Message;
import org.jivesoftware.smack.packet.Stanza;
import org.jivesoftware.smack.tcp.XMPPTCPConnection;
import org.jivesoftware.smack.tcp.XMPPTCPConnectionConfiguration;
import org.jivesoftware.smackx.carbons.packet.CarbonExtension;
import org.jivesoftware.smackx.omemo.OmemoManager;
import org.jivesoftware.smackx.omemo.OmemoMessage;
import org.jivesoftware.smackx.omemo.internal.OmemoDevice;
import org.jivesoftware.smackx.omemo.listener.OmemoMessageListener;
import org.jivesoftware.smackx.omemo.signal.SignalOmemoService;
import org.jivesoftware.smackx.omemo.trust.OmemoFingerprint;
import org.jivesoftware.smackx.omemo.trust.OmemoTrustCallback;
import org.jivesoftware.smackx.omemo.trust.TrustState;
import org.jxmpp.jid.EntityBareJid;
import org.jxmpp.jid.impl.JidCreate;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

/**
 * Headless legacy OMEMO wire client (eu.siacs.conversations.axolotl) using Smack + libsignal.
 */
public final class LegacyOmemoWireClient {

    private final String implementationId;
    private final Path vendorRoot;
    private final Path dataDir;
    private final EntityBareJid jid;
    private final String password;
    private final String host;
    private final int port;

    private XMPPTCPConnection connection;
    private OmemoManager omemoManager;
    private final AtomicReference<String> lastBody = new AtomicReference<>();
    private CountDownLatch receiveLatch;

    public LegacyOmemoWireClient(
            String implementationId,
            Path vendorRoot,
            Path dataDir,
            EntityBareJid jid,
            String password,
            String host,
            int port
    ) {
        this.implementationId = implementationId;
        this.vendorRoot = vendorRoot;
        this.dataDir = dataDir;
        this.jid = jid;
        this.password = password;
        this.host = host;
        this.port = port;
    }

    public static void ensureOmemoService() {
        try {
            SignalOmemoService.acknowledgeLicense();
            SignalOmemoService.setup();
        } catch (Exception e) {
            throw new IllegalStateException("Failed to setup SignalOmemoService", e);
        }
    }

    public void connect() throws Exception {
        Files.createDirectories(dataDir);
        SmackConfiguration.DEBUG = false;

        XMPPTCPConnectionConfiguration config = XMPPTCPConnectionConfiguration.builder()
                .setHost(host)
                .setPort(port)
                .setXmppDomain(jid.asDomainBareJid())
                .setUsernameAndPassword(jid.getLocalpart(), password)
                .setSecurityMode(org.jivesoftware.smack.ConnectionConfiguration.SecurityMode.disabled)
                .build();

        connection = new XMPPTCPConnection(config);
        omemoManager = OmemoManager.getInstanceFor(connection);

        omemoManager.setTrustCallback(new OmemoTrustCallback() {
            @Override
            public TrustState getTrust(OmemoDevice device, OmemoFingerprint fingerprint) {
                return TrustState.trusted;
            }

            @Override
            public void setTrust(OmemoDevice device, OmemoFingerprint fingerprint, TrustState state) {
                // auto-trust for interop tests
            }
        });

        omemoManager.addOmemoMessageListener(new OmemoMessageListener() {
            @Override
            public void onOmemoMessageReceived(Stanza stanza, OmemoMessage.Received decryptedMessage) {
                String body = decryptedMessage.getBody();
                if (body != null && !body.isBlank()) {
                    lastBody.set(body);
                    if (receiveLatch != null) {
                        receiveLatch.countDown();
                    }
                }
            }

            @Override
            public void onOmemoCarbonCopyReceived(
                    CarbonExtension.Direction direction,
                    Message carbonCopy,
                    Message wrappingMessage,
                    OmemoMessage.Received decryptedCarbonCopy
            ) {
                onOmemoMessageReceived(carbonCopy, decryptedCarbonCopy);
            }
        });

        connection.connect();
        omemoManager.initialize();
        connection.login();
        connection.setReplyTimeout(Duration.ofSeconds(30).toMillis());
    }

    public void sendEncrypted(EntityBareJid peer, String plaintext) throws Exception {
        var builder = connection.getStanzaFactory().buildMessageStanza()
                .to(peer)
                .ofType(Message.Type.chat);
        OmemoMessage.Sent encrypted = omemoManager.encrypt(peer, plaintext);
        Message wire = encrypted.buildMessage(builder, peer);
        connection.sendStanza(wire);
    }

    public boolean awaitBody(String expected, long timeoutSeconds) throws InterruptedException {
        receiveLatch = new CountDownLatch(1);
        long deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(timeoutSeconds);
        while (System.nanoTime() < deadline) {
            if (lastBody.get() != null && lastBody.get().equals(expected)) {
                return true;
            }
            receiveLatch.await(500, TimeUnit.MILLISECONDS);
            receiveLatch = new CountDownLatch(1);
        }
        return lastBody.get() != null && lastBody.get().equals(expected);
    }

    public void disconnect() {
        if (connection != null && connection.isConnected()) {
            connection.disconnect();
        }
    }

    public String vendorRevision() {
        try {
            if (!Files.isDirectory(vendorRoot.resolve(".git"))) {
                return "unknown";
            }
            Process proc = new ProcessBuilder("git", "rev-parse", "HEAD")
                    .directory(vendorRoot.toFile())
                    .redirectErrorStream(true)
                    .start();
            String out = new String(proc.getInputStream().readAllBytes(), StandardCharsets.UTF_8).trim();
            proc.waitFor();
            return out.isEmpty() ? "unknown" : out;
        } catch (Exception e) {
            return "unknown";
        }
    }

    public static LegacyOmemoWireClient fromArgs(String implementationId, Path vendorRoot, String[] args)
            throws Exception {
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
        EntityBareJid jid = JidCreate.entityBareFrom(jidStr);
        return new LegacyOmemoWireClient(implementationId, vendorRoot, dataDir, jid, password, host, port);
    }

    public static int runScenario(String implementationId, Path vendorRoot, String[] args) {
        try {
            LegacyOmemoWireClient.ensureOmemoService();

            String mode = null;
            String peerStr = null;
            String sendBody = null;
            String expectBody = null;
            String[] clientArgs = new String[0];

            int split = -1;
            for (int i = 0; i < args.length; i++) {
                if (args[i].equals("--")) {
                    split = i;
                    break;
                }
            }
            if (split >= 0) {
                String[] modeArgs = new String[split];
                System.arraycopy(args, 0, modeArgs, 0, split);
                clientArgs = new String[args.length - split - 1];
                System.arraycopy(args, split + 1, clientArgs, 0, clientArgs.length);
                for (int i = 0; i < modeArgs.length; i++) {
                    switch (modeArgs[i]) {
                        case "--mode" -> mode = modeArgs[++i];
                        case "--peer" -> peerStr = modeArgs[++i];
                        case "--send" -> sendBody = modeArgs[++i];
                        case "--expect" -> expectBody = modeArgs[++i];
                        default -> throw new IllegalArgumentException("Unknown mode arg: " + modeArgs[i]);
                    }
                }
            }

            LegacyOmemoWireClient client = fromArgs(implementationId, vendorRoot, clientArgs);
            System.out.println("IMPLEMENTATION=" + implementationId);
            System.out.println("VENDOR_REV=" + client.vendorRevision());
            System.out.println("NAMESPACE=eu.siacs.conversations.axolotl");

            client.connect();
            Thread.sleep(2000);

            if ("send-wait".equals(mode)) {
                if (peerStr == null || sendBody == null || expectBody == null) {
                    throw new IllegalArgumentException("send-wait requires --peer --send --expect");
                }
                EntityBareJid peer = JidCreate.entityBareFrom(peerStr);
                client.sendEncrypted(peer, sendBody);
                boolean ok = client.awaitBody(expectBody, 45);
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
                    throw new IllegalArgumentException("send requires --peer --send");
                }
                EntityBareJid peer = JidCreate.entityBareFrom(peerStr);
                client.sendEncrypted(peer, sendBody);
                Thread.sleep(1000);
                client.disconnect();
                System.out.println("OK");
                return 0;
            }

            if ("wait".equals(mode)) {
                if (expectBody == null) {
                    throw new IllegalArgumentException("wait requires --expect");
                }
                boolean ok = client.awaitBody(expectBody, 60);
                client.disconnect();
                if (!ok) {
                    System.err.println("TIMEOUT expected=" + expectBody);
                    return 1;
                }
                System.out.println("OK");
                return 0;
            }

            throw new IllegalArgumentException("Unknown --mode: " + mode);
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace(System.err);
            return 1;
        }
    }
}
