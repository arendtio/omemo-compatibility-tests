// swift-tools-version: 5.9
// Siskin / MartinOMEMO vendor-native wire (macOS). Smack proxy is not used on this path.

import PackageDescription

let package = Package(
    name: "SiskinNativeWire",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "siskin-native-wire", targets: ["SiskinNativeWire"]),
    ],
    dependencies: [
        .package(path: "../../vendor/MartinOMEMO"),
        .package(path: "../../vendor/martin"),
    ],
    targets: [
        .target(
            name: "SiskinNativeWireSupport",
            dependencies: [
                .product(name: "MartinOMEMO", package: "MartinOMEMO"),
                .product(name: "Martin", package: "Martin"),
            ],
            path: "Sources/SiskinNativeWireSupport"
        ),
        .executableTarget(
            name: "SiskinNativeWire",
            dependencies: ["SiskinNativeWireSupport"],
            path: "Sources/SiskinNativeWire"
        ),
        .testTarget(
            name: "SiskinNativeCryptoTests",
            dependencies: [
                "SiskinNativeWireSupport",
                .product(name: "MartinOMEMO", package: "MartinOMEMO"),
            ],
            path: "Tests/SiskinNativeCryptoTests"
        ),
    ]
)
