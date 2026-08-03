import Combine
import Foundation
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
    private var messageModule: MessageModule?
    private var chatManager: DefaultChatManager?
    private var storage: WireOMEMOStorage?
    private var messageCancellable: AnyCancellable?
    private var lastBody: String?
    private let bodyLock = NSLock()

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

    public func connect(remotePeer: BareJID? = nil) async throws {
        let files = WireFileOMEMOStore(accountJid: jid.description, dataDir: dataDir)
        let wireStorage = WireOMEMOStorage(files: files)
        guard let signalContext = SignalContext(withStorage: wireStorage) else {
            throw WireError.signalContextFailed
        }
        wireStorage.setup(withContext: signalContext)
        wireStorage.attachContext(client)
        storage = wireStorage

        let omemo = OMEMOModule(signalContext: signalContext, signalStorage: wireStorage)
        omemoModule = omemo

        let chatStore = DefaultChatStore()
        let chatManager = DefaultChatManager(store: chatStore)
        self.chatManager = chatManager
        let messages = MessageModule(chatManager: chatManager)
        messageModule = messages

        _ = client.modulesManager.register(AuthModule())
        _ = client.modulesManager.register(StreamFeaturesModule())
        _ = client.modulesManager.register(StreamManagementModule(mode: .ack))
        _ = client.modulesManager.register(SaslModule())
        _ = client.modulesManager.register(ResourceBinderModule())
        _ = client.modulesManager.register(SessionEstablishmentModule())
        _ = client.modulesManager.register(DiscoveryModule(identity: DiscoveryModule.Identity(category: "client", type: "pc", name: "siskin-native-wire")))
        _ = client.modulesManager.register(SoftwareVersionModule(version: SoftwareVersionModule.SoftwareVersion(name: "siskin-native-wire", version: "0.1", os: "macOS")))
        _ = client.modulesManager.register(PresenceModule())
        _ = client.modulesManager.register(PubSubModule())
        _ = client.modulesManager.register(messages)
        _ = client.modulesManager.register(omemo)

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

        messageCancellable = messages.messagesPublisher.sink { [weak self] received in
            self?.handleIncoming(received.message)
        }

        try client.login()
        try await waitUntilConnected(timeout: 60)
        try await waitUntilOmemoReady(timeout: 90)
        if let remotePeer, let context = client.context {
            chatManager.createChat(for: context, with: remotePeer)
        }
        try await Task.sleep(nanoseconds: 2_000_000_000)
    }

    private func handleIncoming(_ message: Message) {
        guard let omemo = omemoModule else { return }
        guard let from = message.from?.bareJid else { return }
        do {
            let result = try omemo.decrypt(message: message, from: from)
            switch result {
            case .message(let decrypted):
                if let body = decrypted.message.body {
                    bodyLock.lock()
                    lastBody = body
                    bodyLock.unlock()
                }
            case .transportKey:
                break
            }
        } catch {
            fputs("decrypt error: \(error)\n", stderr)
        }
    }

    public func sendEncrypted(peer: BareJID, plaintext: String) async throws {
        guard let omemo = omemoModule else { throw WireError.notConnected }
        let message = Message()
        message.type = .chat
        message.to = JID(peer)
        message.body = plaintext
        let encrypted = try await omemo.encrypt(message: message, for: [peer])
        try await client.writer.write(stanza: encrypted.message)
    }

    public func awaitBody(_ expected: String, timeoutSeconds: Int) async -> Bool {
        let deadline = Date().addingTimeInterval(TimeInterval(timeoutSeconds))
        while Date() < deadline {
            bodyLock.lock()
            let got = lastBody
            bodyLock.unlock()
            if got == expected { return true }
            try? await Task.sleep(nanoseconds: 500_000_000)
        }
        bodyLock.lock()
        let got = lastBody
        bodyLock.unlock()
        return got == expected
    }

    public func disconnect() async {
        try? await client.disconnect()
    }

    private func waitUntilConnected(timeout: TimeInterval) async throws {
        let start = Date()
        while Date().timeIntervalSince(start) < timeout {
            if client.isConnected { return }
            try await Task.sleep(nanoseconds: 200_000_000)
        }
        throw WireError.timeout("connect")
    }

    private func waitUntilOmemoReady(timeout: TimeInterval) async throws {
        guard let omemo = omemoModule else { return }
        let start = Date()
        while Date().timeIntervalSince(start) < timeout {
            if omemo.isReady { return }
            try await Task.sleep(nanoseconds: 500_000_000)
        }
        throw WireError.timeout("omemo_ready")
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
