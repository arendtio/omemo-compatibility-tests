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
        ConversationsNativeWireMain.runMode(mode);
    }
}
