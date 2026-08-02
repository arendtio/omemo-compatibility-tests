package eu.siacs.conversations.wire;

import org.jivesoftware.smack.packet.Stanza;

/**
 * ejabberd PEP may return full item history; Conversations {@code IqParser.getItem} reads only the
 * first child. Keep the latest pubsub item so device lists and bundles match current PEP state.
 */
public final class PubsubResponseFixer {

    private PubsubResponseFixer() {}

    public static Stanza latestItemOnly(Stanza stanza) {
        if (stanza == null) {
            return null;
        }
        String xml = stanza.toXML().toString();
        if (!xml.contains("<items")) {
            return stanza;
        }
        String fixed = keepLastItemInItems(xml);
        if (fixed.equals(xml)) {
            return stanza;
        }
        try {
            return org.jivesoftware.smack.util.PacketParserUtils.parseStanza(fixed);
        } catch (Exception e) {
            return stanza;
        }
    }

    private static String keepLastItemInItems(String xml) {
        int itemsStart = xml.indexOf("<items");
        if (itemsStart < 0) {
            return xml;
        }
        int itemsEnd = xml.indexOf("</items>", itemsStart);
        if (itemsEnd < 0) {
            return xml;
        }
        String itemsBlock = xml.substring(itemsStart, itemsEnd);
        int firstItem = itemsBlock.indexOf("<item");
        int lastItem = itemsBlock.lastIndexOf("<item");
        if (firstItem < 0 || firstItem == lastItem) {
            return xml;
        }
        int itemsOpenEnd = itemsBlock.indexOf('>') + 1;
        String itemsOpen = itemsBlock.substring(0, itemsOpenEnd);
        String tail = itemsBlock.substring(lastItem);
        int itemClose = tail.indexOf("</item>");
        if (itemClose < 0) {
            return xml;
        }
        String oneItem = tail.substring(0, itemClose + "</item>".length());
        return xml.substring(0, itemsStart)
                + itemsOpen
                + oneItem
                + "</items>"
                + xml.substring(itemsEnd + "</items>".length());
    }
}
