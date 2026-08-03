import Foundation
import Martin
import MartinOMEMO

/// File-backed OMEMO stores for headless wire (mirrors Siskin DBOMEMOStore layout in JSON).
public final class WireFileOMEMOStore {

    public let accountJid: String
    public let root: URL

    public init(accountJid: String, dataDir: URL) {
        self.accountJid = accountJid
        self.root = dataDir
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
    }

    private func file(_ name: String) -> URL {
        root.appendingPathComponent(name)
    }

    private func readJSON(_ name: String) -> [String: Any] {
        guard let data = try? Data(contentsOf: file(name)),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return [:]
        }
        return obj
    }

    private func writeJSON(_ name: String, _ dict: [String: Any]) {
        if let data = try? JSONSerialization.data(withJSONObject: dict) {
            try? data.write(to: file(name))
        }
    }

    var registrationId: UInt32 {
        let id = readJSON("meta.json")["registrationId"] as? UInt ?? 0
        return UInt32(id)
    }

    func setRegistrationId(_ id: UInt32) {
        var meta = readJSON("meta.json")
        meta["registrationId"] = Int(id)
        writeJSON("meta.json", meta)
    }

    func identityKeyPairData() -> Data? {
        readJSON("identity.json")["keyPair"] as? Data
            ?? (readJSON("identity.json")["keyPairBase64"] as? String).flatMap { Data(base64Encoded: $0) }
    }

    func saveIdentityKeyPair(_ data: Data) {
        writeJSON("identity.json", ["keyPairBase64": data.base64EncodedString()])
    }

    func sessionKey(name: String, deviceId: Int32) -> String {
        "\(name)#\(deviceId)"
    }

    func sessionRecord(name: String, deviceId: Int32) -> Data? {
        let sessions = readJSON("sessions.json")
        guard let b64 = sessions[sessionKey(name: name, deviceId: deviceId)] as? String else { return nil }
        return Data(base64Encoded: b64)
    }

    func storeSession(name: String, deviceId: Int32, data: Data) {
        var sessions = readJSON("sessions.json")
        sessions[sessionKey(name: name, deviceId: deviceId)] = data.base64EncodedString()
        writeJSON("sessions.json", sessions)
    }

    func deleteSession(name: String, deviceId: Int32) {
        var sessions = readJSON("sessions.json")
        sessions.removeValue(forKey: sessionKey(name: name, deviceId: deviceId))
        writeJSON("sessions.json", sessions)
    }

    func deleteAllSessions(name: String) {
        var sessions = readJSON("sessions.json")
        sessions.keys.filter { $0.hasPrefix("\(name)#") }.forEach { sessions.removeValue(forKey: $0) }
        writeJSON("sessions.json", sessions)
    }

    func allDeviceIds(name: String, activeAndTrusted: Bool) -> [Int32] {
        let sessions = readJSON("sessions.json")
        let ids: [Int32] = sessions.keys.compactMap { key in
            guard key.hasPrefix("\(name)#") else { return nil }
            return Int32(key.split(separator: "#").last ?? "")
        }
        if !activeAndTrusted { return ids }
        return ids.filter { isIdentityTrusted(name: name, deviceId: $0) }
    }

    func preKeyData(id: UInt32) -> Data? {
        let prekeys = readJSON("prekeys.json")
        guard let b64 = prekeys[String(id)] as? String else { return nil }
        return Data(base64Encoded: b64)
    }

    func storePreKey(id: UInt32, data: Data) {
        var prekeys = readJSON("prekeys.json")
        prekeys[String(id)] = data.base64EncodedString()
        writeJSON("prekeys.json", prekeys)
    }

    func deletePreKey(id: UInt32) {
        var prekeys = readJSON("prekeys.json")
        prekeys.removeValue(forKey: String(id))
        writeJSON("prekeys.json", prekeys)
    }

    func currentPreKeyId() -> UInt32 {
        UInt32(readJSON("meta.json")["currentPreKeyId"] as? UInt ?? 0)
    }

    func setCurrentPreKeyId(_ id: UInt32) {
        var meta = readJSON("meta.json")
        meta["currentPreKeyId"] = Int(id)
        writeJSON("meta.json", meta)
    }

    func signedPreKeyData(id: UInt32) -> Data? {
        let keys = readJSON("signed_prekeys.json")
        guard let b64 = keys[String(id)] as? String else { return nil }
        return Data(base64Encoded: b64)
    }

    func storeSignedPreKey(id: UInt32, data: Data) {
        var keys = readJSON("signed_prekeys.json")
        keys[String(id)] = data.base64EncodedString()
        writeJSON("signed_prekeys.json", keys)
    }

    func countSignedPreKeys() -> Int {
        readJSON("signed_prekeys.json").count
    }

    func identityPublicKey(name: String, deviceId: Int32) -> Data? {
        let identities = readJSON("identities.json")
        guard let entry = identities[sessionKey(name: name, deviceId: deviceId)] as? [String: Any],
              let b64 = entry["publicKey"] as? String else { return nil }
        return Data(base64Encoded: b64)
    }

    func saveIdentityPublicKey(name: String, deviceId: Int32, publicKey: Data, own: Bool) {
        var identities = readJSON("identities.json")
        identities[sessionKey(name: name, deviceId: deviceId)] = [
            "publicKey": publicKey.base64EncodedString(),
            "status": IdentityStatus.verifiedActive.rawValue,
            "own": own,
        ]
        writeJSON("identities.json", identities)
    }

    func setIdentityStatus(name: String, deviceId: Int32, status: IdentityStatus) {
        var identities = readJSON("identities.json")
        let key = sessionKey(name: name, deviceId: deviceId)
        var entry = identities[key] as? [String: Any] ?? [:]
        entry["status"] = status.rawValue
        identities[key] = entry
        writeJSON("identities.json", identities)
    }

    func isIdentityTrusted(name: String, deviceId: Int32) -> Bool {
        let identities = readJSON("identities.json")
        guard let entry = identities[sessionKey(name: name, deviceId: deviceId)] as? [String: Any],
              let status = entry["status"] as? Int else { return true }
        return status >= 0 && status % 2 == 0
    }

    func fingerprint(name: String, deviceId: Int32) -> String? {
        guard let pub = identityPublicKey(name: name, deviceId: deviceId) else { return nil }
        return pub.map { String(format: "%02x", $0) }.joined()
    }
}

final class WireIdentityKeyStore: SignalIdentityKeyStoreProtocol {
    weak var context: Martin.Context?
    let files: WireFileOMEMOStore

    init(files: WireFileOMEMOStore) {
        self.files = files
    }

    func keyPair() -> SignalIdentityKeyPairProtocol? {
        guard let data = files.identityKeyPairData() else { return nil }
        return try? SignalIdentityKeyPair(fromKeyPairData: data)
    }

    func localRegistrationId() -> UInt32 { files.registrationId }

    func save(identity: SignalAddress, key: SignalIdentityKeyProtocol?) -> Bool {
        guard let key else { return false }
        if let pairData = (key as? SignalIdentityKeyPairProtocol)?.keyPairData {
            files.saveIdentityKeyPair(pairData)
        }
        return save(identity: identity, publicKeyData: key.publicKeyData)
    }

    func save(identity: SignalAddress, publicKeyData: Data?) -> Bool {
        guard let publicKeyData else { return false }
        files.saveIdentityPublicKey(name: identity.name, deviceId: identity.deviceId, publicKey: publicKeyData, own: true)
        return true
    }

    func isTrusted(identity: SignalAddress, key: SignalIdentityKeyProtocol?) -> Bool { true }
    func isTrusted(identity: SignalAddress, publicKeyData: Data?) -> Bool { true }

    func setStatus(_ status: IdentityStatus, forIdentity: SignalAddress) -> Bool {
        files.setIdentityStatus(name: forIdentity.name, deviceId: forIdentity.deviceId, status: status)
        return true
    }

    func setStatus(active: Bool, forIdentity: SignalAddress) -> Bool {
        setStatus(active ? .verifiedActive : .compromisedInactive, forIdentity: forIdentity)
    }

    func identities(forName name: String) -> [Identity] {
        files.allDeviceIds(name: name, activeAndTrusted: false).compactMap { deviceId in
            guard let pub = files.identityPublicKey(name: name, deviceId: deviceId) else { return nil }
            return Identity(
                address: SignalAddress(name: name, deviceId: deviceId),
                status: .verifiedActive,
                fingerprint: files.fingerprint(name: name, deviceId: deviceId) ?? "",
                key: pub,
                own: name == files.accountJid
            )
        }
    }

    func identityFingerprint(forAddress address: SignalAddress) -> String? {
        files.fingerprint(name: address.name, deviceId: address.deviceId)
    }
}

final class WireSessionStore: SignalSessionStoreProtocol {
    weak var context: Martin.Context?
    let files: WireFileOMEMOStore

    init(files: WireFileOMEMOStore) {
        self.files = files
    }

    func sessionRecord(forAddress address: SignalAddress) -> Data? {
        files.sessionRecord(name: address.name, deviceId: address.deviceId)
    }

    func allDevices(for name: String, activeAndTrusted: Bool) -> [Int32] {
        files.allDeviceIds(name: name, activeAndTrusted: activeAndTrusted)
    }

    func storeSessionRecord(_ data: Data, forAddress address: SignalAddress) -> Bool {
        files.storeSession(name: address.name, deviceId: address.deviceId, data: data)
        return true
    }

    func containsSessionRecord(forAddress address: SignalAddress) -> Bool {
        sessionRecord(forAddress: address) != nil
    }

    func deleteSessionRecord(forAddress address: SignalAddress) -> Bool {
        files.deleteSession(name: address.name, deviceId: address.deviceId)
        return true
    }

    func deleteAllSessions(for name: String) -> Bool {
        files.deleteAllSessions(name: name)
        return true
    }
}

final class WirePreKeyStore: SignalPreKeyStoreProtocol {
    weak var context: Martin.Context?
    let files: WireFileOMEMOStore
    private var pendingDeletes: [UInt32] = []

    init(files: WireFileOMEMOStore) {
        self.files = files
    }

    func currentPreKeyId() -> UInt32 { files.currentPreKeyId() }
    func loadPreKey(withId: UInt32) -> Data? { files.preKeyData(id: withId) }
    func storePreKey(_ data: Data, withId: UInt32) -> Bool {
        files.storePreKey(id: withId, data: data)
        files.setCurrentPreKeyId(withId)
        return true
    }
    func containsPreKey(withId: UInt32) -> Bool { files.preKeyData(id: withId) != nil }
    func deletePreKey(withId: UInt32) -> Bool {
        pendingDeletes.append(withId)
        return true
    }
    func flushDeletedPreKeys() -> Bool {
        pendingDeletes.forEach { files.deletePreKey(id: $0) }
        pendingDeletes.removeAll()
        return true
    }
}

final class WireSignedPreKeyStore: SignalSignedPreKeyStoreProtocol {
    weak var context: Martin.Context?
    let files: WireFileOMEMOStore

    init(files: WireFileOMEMOStore) {
        self.files = files
    }

    func countSignedPreKeys() -> Int { files.countSignedPreKeys() }
    func loadSignedPreKey(withId: UInt32) -> Data? { files.signedPreKeyData(id: withId) }
    func storeSignedPreKey(_ data: Data, withId: UInt32) -> Bool {
        files.storeSignedPreKey(id: withId, data: data)
        return true
    }
    func containsSignedPreKey(withId: UInt32) -> Bool { files.signedPreKeyData(id: withId) != nil }
    func deleteSignedPreKey(withId: UInt32) -> Bool { true }
}

final class WireSenderKeyStore: SignalSenderKeyStoreProtocol {
    func storeSenderKey(_ key: Data, address: SignalAddress?, groupId: String?) -> Bool { true }
    func loadSenderKey(forAddress: SignalAddress?, groupId: String?) -> Data? { nil }
}

public final class WireOMEMOStorage: SignalStorage {
    weak var wireContext: Martin.Context?
    private var signalCtx: SignalContext?
    public let files: WireFileOMEMOStore

    public init(files: WireFileOMEMOStore) {
        let session = WireSessionStore(files: files)
        let preKey = WirePreKeyStore(files: files)
        let signed = WireSignedPreKeyStore(files: files)
        let identity = WireIdentityKeyStore(files: files)
        self.files = files
        super.init(
            sessionStore: session,
            preKeyStore: preKey,
            signedPreKeyStore: signed,
            identityKeyStore: identity,
            senderKeyStore: WireSenderKeyStore()
        )
    }

    public override func setup(withContext context: SignalContext) {
        signalCtx = context
        _ = regenerateKeys(wipe: false)
        super.setup(withContext: context)
    }

    public override func regenerateKeys(wipe: Bool = false) -> Bool {
        guard let signalCtx else { return false }
        if wipe {
            try? FileManager.default.removeItem(at: files.root)
            try? FileManager.default.createDirectory(at: files.root, withIntermediateDirectories: true)
        }
        if identityKeyStore.localRegistrationId() == 0 || identityKeyStore.keyPair() == nil {
            let regId = signalCtx.generateRegistrationId()
            files.setRegistrationId(regId)
            do {
                let keyPair = try SignalIdentityKeyPair.generateKeyPair(context: signalCtx)
                if let pairData = keyPair.keyPairData {
                    files.saveIdentityKeyPair(pairData)
                }
                let addr = SignalAddress(name: files.accountJid, deviceId: Int32(bitPattern: regId))
                identityKeyStore.save(identity: addr, key: keyPair)
            } catch {
                fputs("regenerateKeys failed: \(error)\n", stderr)
                fflush(stderr)
                return false
            }
        }
        return true
    }

    func attachContext(_ context: Martin.Context) {
        wireContext = context
        (sessionStore as? WireSessionStore)?.context = context
        (preKeyStore as? WirePreKeyStore)?.context = context
        (signedPreKeyStore as? WireSignedPreKeyStore)?.context = context
        (identityKeyStore as? WireIdentityKeyStore)?.context = context
    }
}
