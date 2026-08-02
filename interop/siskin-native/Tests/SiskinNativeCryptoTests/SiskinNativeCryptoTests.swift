import XCTest
import MartinOMEMO
import SiskinNativeWireSupport

/// Native MartinOMEMO / libsignal smoke test (macOS). Full wire proof is `siskin-native-wire` + matrix.
final class SiskinNativeCryptoTests: XCTestCase {

    func testSignalIdentityKeyPairGeneration() throws {
        let files = WireFileOMEMOStore(accountJid: "alice@localhost", dataDir: tmpDir())
        let storage = WireOMEMOStorage(files: files)
        guard let ctx = SignalContext(withStorage: storage) else {
            XCTFail("SignalContext")
            return
        }
        storage.setup(withContext: ctx)
        XCTAssertGreaterThan(storage.identityKeyStore.localRegistrationId(), 0)
        XCTAssertNotNil(storage.identityKeyStore.keyPair())
        let reg = storage.identityKeyStore.localRegistrationId()
        let pair = try SignalIdentityKeyPair.generateKeyPair(context: ctx)
        XCTAssertNotNil(pair.publicKeyData)
        XCTAssertEqual(storage.identityKeyStore.localRegistrationId(), reg)
    }

    private func tmpDir() -> URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("siskin-native-\(UUID().uuidString)")
    }
}
