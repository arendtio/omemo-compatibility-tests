package eu.siacs.conversations.wire;

import java.io.ByteArrayOutputStream;
import java.io.IOException;

import im.conversations.android.xmpp.StreamElementWriter;
import im.conversations.android.xmpp.model.StreamElement;
import im.conversations.android.xml.XmlElementReader;

import org.jivesoftware.smack.packet.Stanza;
import org.jivesoftware.smack.util.PacketParserUtils;

/** Converts between Tigase/Conversations {@link StreamElement} and Smack {@link Stanza}. */
public final class SmackXmlBridge {

    private SmackXmlBridge() {}

    public static String toXml(StreamElement element) throws IOException {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        StreamElementWriter writer = new StreamElementWriter(bos);
        writer.write(element);
        writer.flush();
        return bos.toString();
    }

    public static Stanza toSmackStanza(StreamElement element) throws Exception {
        return PacketParserUtils.parseStanza(toXml(element));
    }

  @SuppressWarnings("unchecked")
    public static <T extends StreamElement> T fromSmackStanza(Stanza stanza, Class<T> type)
            throws Exception {
        String xml = stanza.toXML().toString();
        return XmlElementReader.read(xml, type);
    }
}
