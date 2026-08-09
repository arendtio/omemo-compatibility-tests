import Foundation
import Martin

/// In-memory roster store for wire interop (DefaultRosterStore init is internal).
final class WireRosterStore: RosterStore {
    typealias RosterItem = RosterItemBase

    private var roster = [JID: RosterItem]()
    private var version: String?
    private let dispatcher = DispatchQueue(label: "WireRosterStore")

    func clear(for context: Context) {
        dispatcher.async {
            self.version = nil
            self.roster.removeAll()
        }
    }

    func items(for context: Context) -> [RosterItemBase] {
        dispatcher.sync {
            Array(roster.values)
        }
    }

    func item(for context: Context, jid: JID) -> RosterItemBase? {
        dispatcher.sync {
            roster[jid]
        }
    }

    func updateItem(
        for context: Context,
        jid: JID,
        name: String?,
        subscription: RosterItemSubscription,
        groups: [String],
        ask: Bool,
        annotations: [RosterItemAnnotation]
    ) {
        let item = RosterItemBase(
            jid: jid,
            name: name,
            subscription: subscription,
            groups: groups,
            ask: ask,
            annotations: annotations
        )
        dispatcher.async {
            self.roster[jid] = item
        }
    }

    func deleteItem(for context: Context, jid: JID) {
        dispatcher.async {
            self.roster.removeValue(forKey: jid)
        }
    }

    func version(for context: Context) -> String? {
        dispatcher.sync {
            version
        }
    }

    func set(version: String?, for context: Context) {
        dispatcher.async {
            self.version = version
        }
    }

    func initialize(context: Context) {}

    func deinitialize(context: Context) {}
}
