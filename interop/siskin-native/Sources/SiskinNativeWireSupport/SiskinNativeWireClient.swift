import Foundation
import Combine
import Martin
import MartinOMEMO

public final class SiskinNativeWireClient {

    public let jid: BareJID
    public let password: String
    public let host: String
    public let port: Int
    public let dataDir: URL

    private let client = XMPPClient()
    private var omemoModule: OMEMOModule?
    private var storage: WireOMEMOStorage?
    private var wireIncomingModule: WireIncomingMessageModule?
    private let bodyQueue = DispatchQueue(label: "siskin-native-wire.body")
    private var lastBody: String?
    private var cancellables = Set<AnyCancellable>()

    public init(jid: BareJID, password: String, host: String, port: Int, dataDir: URL) {
        self.jid = jid
        self.password = password
        self.host = host
        self.port = port
        self.dataDir = dataDir
    }

    public func vendorRevision() -> String {
        let root = ProcessInfo.processInfo.environment["OMEMO_INTEROP_ROOT"] ?? ".."
        let vendor = URL(fileURLWithPath: root).appendingPathComponent("vendor/siskin_im")
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/git")
        proc.arguments = ["rev-parse", "HEAD"]
        proc.currentDirectoryURL = vendor
        let pipe = Pipe()
        proc.standardOutput = pipe
        try? proc.run()
        proc.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let rev = String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return rev.isEmpty ? "unknown" : rev
    }

    @MainActor
    public func connect() async throws {
        WireLog.line("connect: begin")
        let files = WireFileOMEMOStore(accountJid: jid.description, dataDir: dataDir)
        WireLog.line("connect: storage files ready")
        let wireStorage = WireOMEMOStorage(files: files)
        guard let signalContext = SignalContext(withStorage: wireStorage) else {
            throw WireError.signalContextFailed
        }
        WireLog.line("connect: signal context ready")
        wireStorage.setup(withContext: signalContext)
        wireStorage.attachContext(client)
        storage = wireStorage

        let omemo = OMEMOModule(signalContext: signalContext, signalStorage: wireStorage)
        omemoModule = omemo

        let wireIncoming = WireIncomingMessageModule()
        wireIncoming.onMessage = { [weak self] message in
            self?.handleIncoming(message)
        }
        wireIncomingModule = wireIncoming

        _ = client.modulesManager.register(AuthModule())
        _ = client.modulesManager.register(StreamFeaturesModule())
        _ = client.modulesManager.register(StreamManagementModule(mode: .ack))
        _ = client.modulesManager.register(SaslModule())
        _ = client.modulesManager.register(ResourceBinderModule())
        _ = client.modulesManager.register(SessionEstablishmentModule())
        _ = client.modulesManager.register(DiscoveryModule(identity: DiscoveryModule.Identity(category: "client", type: "pc", name: "siskin-native-wire")))
        _ = client.modulesManager.register(SoftwareVersionModule(version: SoftwareVersionModule.SoftwareVersion(name: "siskin-native-wire", version: "0.1", os: "macOS")))
        _ = client.modulesManager.register(PresenceModule())
        client.module(.presence).subscriptionPublisher.sink { [weak self] change in
            guard let self, change.action == .subscribe else { return }
            Task { @MainActor in
                let presence = self.client.module(.presence)
                try? await presence.subscribed(by: change.jid)
                try? await presence.subscribe(to: change.jid)
                WireLog.line("auto-accept subscription from \(change.jid)")
            }
        }.store(in: &cancellables)
        _ = client.modulesManager.register(PubSubModule())
        _ = client.modulesManager.register(RosterModule(rosterManager: RosterManagerBase(store: WireRosterStore())))
        _ = client.modulesManager.register(wireIncoming)
        _ = client.modulesManager.register(omemo)
        WireLog.line("connect: modules registered")

        client.connectionConfiguration.userJid = jid
        client.connectionConfiguration.credentials = .password(password)
        client.connectionConfiguration.disableCompression = true

        let tlsMode = ProcessInfo.processInfo.environment["OMEMO_XMPP_SECURITY"] ?? "auto"
        if tlsMode == "disabled" {
            client.connectionConfiguration.disableTLS = true
        }

        client.connectionConfiguration.modifyConnectorOptions(type: SocketConnectorNetwork.Options.self) { options in
            options.connectionDetails = SocketConnectorNetwork.Endpoint(proto: .XMPP, host: host, port: port)
            options.sslCertificateValidation = .customValidator({ _ in true })
            options.connectionTimeout = 30
        }

        try client.login()
        WireLog.line("connect: logged in")
        try await waitUntilConnected(timeout: 60)
        WireLog.line("connect: xmpp connected")

        try await waitUntilOmemoReady(timeout: 120)
        WireLog.line("connect: omemo ready")
        try await client.module(.presence).sendPresence()
        WireLog.line("connect: presence sent")
        pumpRunLoop(seconds: 2)
    }

    @MainActor
    public func ensureRosterPeer(_ peer: BareJID) async throws {
        let roster = client.module(.roster)
        let peerJid = JID(peer)
        if roster.rosterManager.items(for: client.context).contains(where: { $0.jid == peerJid }) {
            return
        }
        WireLog.line("ensureRosterPeer: adding \(peer)")
        do {
            try await withThrowingTaskGroup(of: Void.self) { group in
                group.addTask { @MainActor in
                    _ = try await roster.addItem(jid: peerJid, name: peer.localPart, groups: [])
                }
                group.addTask {
                    try await Task.sleep(nanoseconds: 15_000_000_000)
                    throw WireError.timeout("roster_add")
                }
                try await group.next()
                group.cancelAll()
            }
        } catch {
            WireLog.line("ensureRosterPeer: \(error)")
        }
        pumpRunLoop(seconds: 1)
    }

    @MainActor
    public func waitForOwnOmemoPublish() async throws {
        guard let omemo = omemoModule else { throw WireError.notConnected }
        WireLog.line("waitForOwnOmemoPublish")
        let deadline = Date().addingTimeInterval(90)
        while Date() < deadline {
            if omemo.isReady {
                pumpRunLoop(seconds: 8)
                WireLog.line("waitForOwnOmemoPublish: done")
                return
            }
            pumpRunLoop(seconds: 0.5)
        }
        throw WireError.timeout("own_omemo_publish")
    }

    @MainActor
    public func waitForPeerOmemoReady(peer: BareJID, timeoutSeconds: Int) async throws {
        guard let omemo = omemoModule, let storage else {
            throw WireError.notConnected
        }
        WireLog.line("waitForPeerOmemoReady: \(peer)")
        let deadline = Date().addingTimeInterval(TimeInterval(timeoutSeconds))
        while Date() < deadline {
            let addresses = try await omemo.addresses(for: [peer])
            if !addresses.isEmpty {
                var allReady = true
                for address in addresses {
                    _ = storage.identityKeyStore.setStatus(.verifiedActive, forIdentity: address)
                    if !storage.sessionStore.containsSessionRecord(forAddress: address) {
                        try await regenerateSessionWithTimeout(omemo: omemo, address: address, timeoutSeconds: 30)
                    }
                    if !storage.sessionStore.containsSessionRecord(forAddress: address) {
                        allReady = false
                    }
                }
                if allReady {
                    WireLog.line("waitForPeerOmemoReady: ready (\(addresses.count) device(s))")
                    return
                }
            }
            pumpRunLoop(seconds: 0.5)
        }
        throw WireError.timeout("peer_omemo_ready")
    }

    @MainActor
    public func writeReadyMarker() throws {
        try "ok".write(to: dataDir.appendingPathComponent("wire-ready"), atomically: true, encoding: .utf8)
        WireLog.line("READY")
    }

    @MainActor
    public func waitForSendSignal(timeoutSeconds: Int = 600) async throws {
        let signal = dataDir.appendingPathComponent("wire-send-now")
        let deadline = Date().addingTimeInterval(TimeInterval(timeoutSeconds))
        while Date() < deadline {
            if FileManager.default.fileExists(atPath: signal.path) {
                try? FileManager.default.removeItem(at: signal)
                return
            }
            pumpRunLoop(seconds: 0.25)
        }
        throw WireError.timeout("wire-send-now")
    }

    private func handleIncoming(_ message: Message) {
        guard let omemo = omemoModule else { return }
        guard let from = message.from?.bareJid else { return }
        WireLog.line("incoming: from=\(from)")
        do {
            let result = try omemo.decrypt(message: message, from: from)
            switch result {
            case .message(let decrypted):
                if let body = decrypted.message.body {
                    WireLog.line("incoming: body=\(body)")
                    noteBody(body)
                }
            case .transportKey:
                WireLog.line("incoming: transportKey")
                break
            }
        } catch {
            WireLog.line("decrypt error: \(error)")
        }
    }

    @MainActor
    public func sendEncrypted(peer: BareJID, plaintext: String) async throws {
        guard let omemo = omemoModule else { throw WireError.notConnected }
        try await ensureRosterPeer(peer)
        try await waitForPeerOmemoReady(peer: peer, timeoutSeconds: 60)
        let message = Message()
        message.type = .chat
        message.to = JID(peer)
        message.body = plaintext
        let encrypted = try await omemo.encrypt(message: message, for: [peer])
        try await client.writer.write(stanza: encrypted.message)
        pumpRunLoop(seconds: 1)
    }

    @MainActor
    public func awaitBody(_ expected: String, timeoutSeconds: Int) async -> Bool {
        let deadline = Date().addingTimeInterval(TimeInterval(timeoutSeconds))
        while Date() < deadline {
            if currentBody() == expected { return true }
            pumpRunLoop(seconds: 0.25)
        }
        return currentBody() == expected
    }

    private func noteBody(_ body: String) {
        bodyQueue.sync { lastBody = body }
    }

    private func currentBody() -> String? {
        bodyQueue.sync { lastBody }
    }

    @MainActor
    public func disconnect() async {
        try? await client.disconnect()
    }

    @MainActor
    private func waitUntilConnected(timeout: TimeInterval) async throws {
        let start = Date()
        while Date().timeIntervalSince(start) < timeout {
            if client.isConnected { return }
            pumpRunLoop(seconds: 0.2)
        }
        throw WireError.timeout("connect")
    }

    @MainActor
    private func waitUntilOmemoReady(timeout: TimeInterval) async throws {
        guard let omemo = omemoModule else { return }
        let start = Date()
        while Date().timeIntervalSince(start) < timeout {
            if omemo.isReady { return }
            pumpRunLoop(seconds: 0.5)
        }
        throw WireError.timeout("omemo_ready")
    }

    @MainActor
    private func regenerateSessionWithTimeout(omemo: OMEMOModule, address: SignalAddress, timeoutSeconds: Int) async throws {
        try await withThrowingTaskGroup(of: Void.self) { group in
            group.addTask { @MainActor in
                try await omemo.regenerateSession(forAddress: address)
            }
            group.addTask {
                try await Task.sleep(nanoseconds: UInt64(timeoutSeconds) * 1_000_000_000)
                throw WireError.timeout("regenerate_session")
            }
            try await group.next()
            group.cancelAll()
        }
    }

    @MainActor
    private func pumpRunLoop(seconds: TimeInterval) {
        RunLoop.main.run(mode: .default, before: Date(timeIntervalSinceNow: seconds))
    }

    public static func awaitTimeoutSeconds() -> Int {
        let env = ProcessInfo.processInfo.environment
        for key in ["SISKIN_WIRE_AWAIT_TIMEOUT", "CONVERSATIONS_WIRE_AWAIT_TIMEOUT"] {
            if let raw = env[key], let value = Int(raw), value > 0 {
                return value
            }
        }
        return 600
    }
}

public enum WireError: Error, CustomStringConvertible {
    case signalContextFailed
    case notConnected
    case timeout(String)

    public var description: String {
        switch self {
        case .signalContextFailed: return "SignalContext init failed"
        case .notConnected: return "not connected"
        case .timeout(let what): return "timeout waiting for \(what)"
        }
    }
}
