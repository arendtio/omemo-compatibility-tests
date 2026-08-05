#import <Foundation/Foundation.h>
#import <monalxmpp/xmpp.h>

NS_ASSUME_NONNULL_BEGIN

/// Redirect Monal DataLayer / HelperTools container to a wire data directory.
void MonalWireBootstrapInstall(NSURL* dataDir);

/// Install MLStream TLS stubs once monalxmpp is fully loaded (safe to call repeatedly).
void MonalWireEnsurePlaintextHooks(void);

/// SASL2 on ejabberd may leave the account at kStateLoggedIn without bind; send legacy bind IQ.
void MonalWireTriggerLegacyBindAfterSasl2(xmpp* account);
void MonalWireForcePlaintextStreamReady(xmpp* account);

/// Run block on Monal's XMPP receive queue (required for bind/session ops).
void MonalWireDispatchOnReceiveQueue(xmpp* account, void (^block)(void));

NS_ASSUME_NONNULL_END
