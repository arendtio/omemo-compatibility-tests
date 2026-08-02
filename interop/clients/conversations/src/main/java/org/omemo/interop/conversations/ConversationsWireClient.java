package org.omemo.interop.conversations;

import org.omemo.interop.LegacyOmemoWireClient;

import java.nio.file.Path;

/**
 * Headless wire client bound to the Conversations vendor checkout.
 * Uses legacy OMEMO (eu.siacs.conversations.axolotl) via the same signal-protocol
 * stack as Conversations (org.whispersystems:signal-protocol-java).
 */
public final class ConversationsWireClient {

    private static Path vendorRoot(String implId) {
        String root = System.getenv("OMEMO_INTEROP_ROOT");
        Path base = root != null ? Path.of(root) : Path.of(".").toAbsolutePath().normalize();
        return base.resolve("vendor").resolve(implId);
    }

    public static void main(String[] args) {
        int code = LegacyOmemoWireClient.runScenario("conversations", vendorRoot("conversations"), args);
        System.exit(code);
    }
}
