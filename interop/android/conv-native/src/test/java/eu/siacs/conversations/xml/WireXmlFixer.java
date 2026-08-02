package eu.siacs.conversations.xml;

import eu.siacs.conversations.crypto.axolotl.AxolotlService;

/** Aligns in-memory {@link Element} trees with on-wire OMEMO payload namespace. */
public final class WireXmlFixer {

    private WireXmlFixer() {}

    public static Element fixOmemoPayloadNamespace(Element encrypted) {
        Element payload = encrypted.findChild("payload");
        if (payload == null) {
            return encrypted;
        }
        encrypted.children.remove(payload);
        encrypted.addChild("payload", AxolotlService.PEP_PREFIX).setContent(payload.getContent());
        return encrypted;
    }
}
