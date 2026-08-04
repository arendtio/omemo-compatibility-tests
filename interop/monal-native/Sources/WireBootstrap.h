#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

/// Redirect Monal DataLayer / HelperTools container to a wire data directory.
void MonalWireBootstrapInstall(NSURL* dataDir);

/// Install MLStream TLS stubs once monalxmpp is fully loaded (safe to call repeatedly).
void MonalWireEnsurePlaintextHooks(void);

NS_ASSUME_NONNULL_END
