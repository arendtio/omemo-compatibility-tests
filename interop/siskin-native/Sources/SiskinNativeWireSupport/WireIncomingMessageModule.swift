import Foundation
import Martin

/// Decrypt OMEMO payloads from inbound message stanzas without DefaultChatStore chat pre-creation.
final class WireIncomingMessageModule: XmppModuleBase, XmppStanzaProcessor, @unchecked Sendable {

    static let ID = "wire-incoming-message"

    let id = ID
    let criteria = Criteria.name("message", types: [StanzaType.chat, StanzaType.normal, nil])
    let features: [String] = []

    var onMessage: ((Message) -> Void)?

    func process(stanza: Stanza) async throws {
        onMessage?(stanza as! Message)
    }
}
