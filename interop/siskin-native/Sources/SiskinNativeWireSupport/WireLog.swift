import Foundation

enum WireLog {
    static func line(_ message: String) {
        fputs("\(message)\n", stderr)
        fflush(stderr)
    }
}
