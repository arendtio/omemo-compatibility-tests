import Foundation
import Martin
import MartinOMEMO
import SiskinNativeWireSupport

@main
enum SiskinNativeWireMain {
    static func main() {
        let done = DispatchSemaphore(value: 0)
        var exitCode: Int32 = 1
        Task { @MainActor in
            exitCode = await runScenario(arguments: CommandLine.arguments)
            done.signal()
        }
        while done.wait(timeout: .now() + 0.1) == .timedOut {
            RunLoop.main.run(mode: .default, before: Date(timeIntervalSinceNow: 0.1))
        }
        exit(exitCode)
    }

    @MainActor
    static func runScenario(arguments: [String]) async -> Int32 {
        do {
            var mode: String?
            var peer: String?
            var sendBody: String?
            var expectBody: String?
            var jidStr: String?
            var password: String?
            var host = "127.0.0.1"
            var port = 5222
            var dataDir = URL(fileURLWithPath: "omemo-wire-data")

            var split = -1
            for (i, arg) in arguments.enumerated() {
                if arg == "--" { split = i; break }
            }

            let modeArgs = split >= 0 ? Array(arguments[1..<split]) : []
            let clientArgs = split >= 0 ? Array(arguments[(split + 1)...]) : []

            var i = 0
            while i < modeArgs.count {
                switch modeArgs[i] {
                case "--mode": mode = modeArgs[i + 1]; i += 2
                case "--peer": peer = modeArgs[i + 1]; i += 2
                case "--send": sendBody = modeArgs[i + 1]; i += 2
                case "--expect": expectBody = modeArgs[i + 1]; i += 2
                default:
                    fputs("Unknown mode arg: \(modeArgs[i])\n", stderr)
                    return 1
                }
            }

            i = 0
            while i < clientArgs.count {
                switch clientArgs[i] {
                case "--jid": jidStr = clientArgs[i + 1]; i += 2
                case "--password": password = clientArgs[i + 1]; i += 2
                case "--host": host = clientArgs[i + 1]; i += 2
                case "--port": port = Int(clientArgs[i + 1]) ?? 5222; i += 2
                case "--data-dir": dataDir = URL(fileURLWithPath: clientArgs[i + 1]); i += 2
                default:
                    fputs("Unknown client arg: \(clientArgs[i])\n", stderr)
                    return 1
                }
            }

            guard let jidStr, let password else {
                fputs("--jid and --password required\n", stderr)
                return 1
            }
            let bare = BareJID(jidStr)

            let client = SiskinNativeWireClient(jid: bare, password: password, host: host, port: port, dataDir: dataDir)
            let vendorRev = client.vendorRevision()
            WireLog.line("IMPLEMENTATION=siskin_im")
            WireLog.line("VENDOR_REV=\(vendorRev)")
            WireLog.line("NAMESPACE=eu.siacs.conversations.axolotl")
            WireLog.line("RUNNER=siskin_native_martinomemo")

            let remotePeer = peer.map { BareJID($0) }
            WireLog.line("connect: invoking mode=\(mode ?? "nil") peer=\(peer ?? "nil")")
            try await client.connect(remotePeer: mode == "wait" ? remotePeer : nil)

            switch mode {
            case "send":
                guard let peer, let sendBody else {
                    fputs("send requires --peer --send\n", stderr)
                    return 1
                }
                let peerJid = BareJID(peer)
                try await client.sendEncrypted(peer: peerJid, plaintext: sendBody)
                RunLoop.main.run(mode: .default, before: Date(timeIntervalSinceNow: 1))
                await client.disconnect()
                WireLog.line("OK")
                return 0

            case "wait":
                guard let expectBody else {
                    fputs("wait requires --expect\n", stderr)
                    return 1
                }
                guard peer != nil else {
                    fputs("wait requires --peer (sender JID)\n", stderr)
                    return 1
                }
                let ok = await client.awaitBody(expectBody, timeoutSeconds: 120)
                await client.disconnect()
                if ok {
                    WireLog.line("OK")
                    return 0
                }
                WireLog.line("TIMEOUT expected=\(expectBody)")
                return 1

            case "send-wait":
                guard let peer, let sendBody, let expectBody else {
                    fputs("send-wait requires --peer --send --expect\n", stderr)
                    return 1
                }
                let peerJid = BareJID(peer)
                try await client.sendEncrypted(peer: peerJid, plaintext: sendBody)
                let ok = await client.awaitBody(expectBody, timeoutSeconds: 45)
                await client.disconnect()
                if ok {
                    WireLog.line("OK")
                    return 0
                }
                WireLog.line("TIMEOUT expected=\(expectBody)")
                return 1

            default:
                fputs("Unknown --mode: \(mode ?? "nil")\n", stderr)
                return 1
            }
        } catch {
            WireLog.line("ERROR: \(error)")
            return 1
        }
    }
}
