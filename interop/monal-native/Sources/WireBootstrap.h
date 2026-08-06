#import <Foundation/Foundation.h>
#import <monalxmpp/xmpp.h>

NS_ASSUME_NONNULL_BEGIN

/// Redirect Monal DataLayer / HelperTools container to a wire data directory.
void MonalWireBootstrapInstall(NSURL* dataDir);

/// Delete and re-seed sworim.sqlite (used between connect retries).
void MonalWireResetDataStore(NSURL* dataDir);

/// Install MLStream TLS stubs once monalxmpp is fully loaded (safe to call repeatedly).
void MonalWireEnsurePlaintextHooks(void);

/// Fallback when still at kStateLoggedIn without bind; sends legacy bind IQ on receive queue.
void MonalWireTriggerLegacyBindAfterSasl2(xmpp* account);

/// Keep plaintext stream features on the secure processing path (ejabberd has no STARTTLS).
void MonalWireForcePlaintextStreamReady(xmpp* account);

/// Run block on Monal's XMPP receive queue (required for bind/session ops).
void MonalWireDispatchOnReceiveQueue(xmpp* account, void (^block)(void));

NS_ASSUME_NONNULL_END
