import Foundation

public enum WireLog {
    public static func line(_ message: String) {
        fputs("\(message)\n", stderr)
        fflush(stderr)
    }
}
