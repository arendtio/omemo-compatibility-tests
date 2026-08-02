package eu.siacs.conversations.crypto.axolotl;

import android.os.Build;

import org.junit.Test;
import org.junit.runner.RunWith;
import org.robolectric.RobolectricTestRunner;
import org.robolectric.annotation.ConscryptMode;
import org.robolectric.annotation.Config;

@RunWith(RobolectricTestRunner.class)
@Config(sdk = Build.VERSION_CODES.P)
@ConscryptMode(ConscryptMode.Mode.OFF)
public class ConversationsNativeWireMainTest {

    @Test
    public void runNativeWireMain() throws Exception {
        String mode = System.getProperty("wire.mode", "local_roundtrip");
        String[] clientArgs = wireClientArgs();
        ConversationsNativeWireMain.runMode(mode, clientArgs);
    }

    private static String[] wireClientArgs() {
        String jid = System.getProperty("wire.jid");
        String password = System.getProperty("wire.password");
        if (jid == null || password == null) {
            return new String[] {
                "--jid", "alice@localhost",
                "--password", "alicepass",
                "--host", System.getProperty("wire.host", "127.0.0.1"),
                "--port", System.getProperty("wire.port", "5222"),
                "--data-dir", System.getProperty("wire.dataDir", "/tmp/conv-native-wire"),
            };
        }
        return new String[] {
            "--jid", jid,
            "--password", password,
            "--host", System.getProperty("wire.host", "127.0.0.1"),
            "--port", System.getProperty("wire.port", "5222"),
            "--data-dir", System.getProperty("wire.dataDir", "/tmp/conv-native-wire"),
        };
    }
}
