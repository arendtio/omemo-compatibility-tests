package org.omemo.interop.siskin;

import org.omemo.interop.LegacyOmemoWireClient;

import java.nio.file.Path;

/**
 * Headless wire client bound to the Siskin IM vendor checkout.
 * Uses legacy OMEMO wire format (eu.siacs.conversations.axolotl) via Smack + libsignal
 * for cross-client ejabberd tests until a native Tigase Swift runner is available.
 */
public final class SiskinWireClient {

    private static Path vendorRoot(String implId) {
        String root = System.getenv("OMEMO_INTEROP_ROOT");
        Path base = root != null ? Path.of(root) : Path.of(".").toAbsolutePath().normalize();
        return base.resolve("vendor").resolve(implId);
    }

    public static void main(String[] args) {
        int code = LegacyOmemoWireClient.runScenario("siskin_im", vendorRoot("siskin_im"), args);
        System.exit(code);
    }
}
