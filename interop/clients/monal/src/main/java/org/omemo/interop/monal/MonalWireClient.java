package org.omemo.interop.monal;

import org.omemo.interop.LegacyOmemoWireClient;

import java.nio.file.Path;

/**
 * Headless wire client bound to the Monal vendor checkout.
 * Monal implements legacy axolotl OMEMO in MLOMEMO.m; this runner uses the same
 * wire namespace and libsignal family as Monal for cross-client ejabberd tests.
 */
public final class MonalWireClient {

    private static Path vendorRoot(String implId) {
        String root = System.getenv("OMEMO_INTEROP_ROOT");
        Path base = root != null ? Path.of(root) : Path.of(".").toAbsolutePath().normalize();
        return base.resolve("vendor").resolve(implId);
    }

    public static void main(String[] args) {
        int code = LegacyOmemoWireClient.runScenario("monal", vendorRoot("monal"), args);
        System.exit(code);
    }
}
