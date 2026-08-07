package eu.siacs.conversations.crypto.axolotl;

import eu.siacs.conversations.wire.NativeWireClient;
import eu.siacs.conversations.xml.Element;

/**
 * CLI entry for pytest / wire_client when Robolectric is booted via Gradle Test task.
 */
public final class ConversationsNativeWireMain {

    private ConversationsNativeWireMain() {}

    public static void main(String[] args) throws Exception {
        runMode(System.getProperty("wire.mode", "local_roundtrip"), args);
    }

    static void runMode(String mode, String[] clientArgs) throws Exception {
        switch (mode) {
            case "local_roundtrip":
                String plaintext = ConversationsNativeRoundtrip.roundtrip("native-wire-roundtrip");
                if (!"native-wire-roundtrip".equals(plaintext)) {
                    throw new IllegalStateException("roundtrip mismatch: " + plaintext);
                }
                System.out.println("OK");
                System.out.println("RUNNER=conversations_android_crypto NATIVE=VENDOR_AXOLOTL");
                return;
            case "export_xml":
                Element wire = ConversationsNativeRoundtrip.exportVendorXml("slixmpp-cross-decrypt-body");
                System.out.println("VENDOR_XML=" + wire.toString());
                System.out.println("RUNNER=conversations_android_crypto NATIVE=VENDOR_AXOLOTL");
                return;
            case "publish":
            case "send":
            case "wait":
            case "send-wait":
                System.setProperty("wire.mode", mode);
                int code = NativeWireClient.runScenario(clientArgs);
                if (code != 0) {
                    throw new IllegalStateException("native wire failed with code " + code);
                }
                return;
            default:
                throw new IllegalArgumentException("Unknown wire.mode=" + mode);
        }
    }
}
