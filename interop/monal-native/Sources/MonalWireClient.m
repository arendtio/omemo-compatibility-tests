#import "MonalWireClient.h"
#import "WireBootstrap.h"
#import "MonalWireLog.h"
#import <monalxmpp/DataLayer.h>
#import <monalxmpp/HelperTools.h>
#import <monalxmpp/MLXMPPManager.h>
#import <monalxmpp/MLContact.h>
#import <monalxmpp/MLMessage.h>
#import <monalxmpp/MLConstants.h>
#import <monalxmpp/MLNotificationQueue.h>
#import <monalxmpp/MLOMEMO.h>
#import <monalxmpp/MLXMLNode.h>
#import <monalxmpp/xmpp.h>
#import <objc/message.h>

@interface MonalWireClient ()
@property(nonatomic, copy) NSString* jid;
@property(nonatomic, copy) NSString* password;
@property(nonatomic, copy) NSString* host;
@property(nonatomic, assign) int port;
@property(nonatomic, strong) NSURL* dataDir;
@property(nonatomic, strong) NSNumber* accountID;
@property(nonatomic, copy) NSString* preparedPeerJid;
@property(nonatomic, copy) NSString* lastBody;
@property(nonatomic, assign) BOOL smacksFallbackScheduled;
@property(nonatomic, assign) BOOL legacyBindTriggered;
@property(nonatomic, strong) NSDate* loggedInSince;
@end

@implementation MonalWireClient

- (instancetype)initWithJid:(NSString*)jid
                     password:(NSString*)password
                         host:(NSString*)host
                         port:(int)port
                      dataDir:(NSURL*)dataDir {
    self = [super init];
    if (self) {
        _jid = [jid copy];
        _password = [password copy];
        _host = [host copy];
        _port = port;
        _dataDir = dataDir;
    }
    return self;
}

- (NSString*)vendorRevision {
    NSString* fromEnv = [NSProcessInfo processInfo].environment[@"MONAL_VENDOR_REV"];
    if (fromEnv.length) {
        return fromEnv;
    }
    NSString* root = [NSProcessInfo processInfo].environment[@"OMEMO_INTEROP_ROOT"];
    if (!root.length) {
        return @"unknown";
    }
    NSString* monal = [root stringByAppendingPathComponent:@"vendor/monal"];
    NSString* headPath = [monal stringByAppendingPathComponent:@".git/HEAD"];
    NSString* head = [NSString stringWithContentsOfFile:headPath encoding:NSUTF8StringEncoding error:nil];
    head = [head stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if (!head.length) {
        return @"unknown";
    }
    if ([head hasPrefix:@"ref: "]) {
        NSString* refRel = [head substringFromIndex:5];
        NSString* refPath = [monal stringByAppendingPathComponent:[NSString stringWithFormat:@".git/%@", refRel]];
        NSString* sha = [NSString stringWithContentsOfFile:refPath encoding:NSUTF8StringEncoding error:nil];
        sha = [sha stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
        return sha.length ? sha : @"unknown";
    }
    return head;
}

- (xmpp*)account {
    return [[MLXMPPManager sharedInstance] getEnabledAccountForID:self.accountID];
}

- (void)handleNewMessage:(NSNotification*) notification {
    NSDictionary* info = notification.userInfo;
    MLMessage* message = info[@"message"];
    if (!message || !message.messageText.length) {
        return;
    }
    self.lastBody = message.messageText;
    MonalWireLog([[NSString stringWithFormat:@"incoming body=%@", message.messageText] UTF8String]);
}

- (BOOL)startAccountLogin {
    MLXMPPManager* manager = [MLXMPPManager sharedInstance];
    NSString* portStr = [NSString stringWithFormat:@"%d", self.port];
    NSNumber* accountID = [manager login:self.jid
                                  password:self.password
                            hardcodedServer:self.host
                            hardcodedPort:portStr
                            forceDirectTLS:NO
                            allowPlainAuth:YES];
    if (accountID == nil) {
        NSArray* elements = [self.jid componentsSeparatedByString:@"@"];
        if ([elements count] > 1) {
            NSString* user = ((NSString*)[elements objectAtIndex:0]).lowercaseString;
            NSString* domain = ((NSString*)[elements objectAtIndex:1]).lowercaseString;
            accountID = [[DataLayer sharedInstance] accountIDForUser:user andDomain:domain];
            if (accountID != nil) {
                [manager addNewAccountToKeychainAndConnectWithPassword:self.password andAccountID:accountID];
            }
        }
    }
    if (accountID == nil) {
        return NO;
    }
    self.accountID = accountID;
    return YES;
}

- (void)resetAccountForRetry {
    if (self.accountID != nil) {
        [[MLXMPPManager sharedInstance] removeAccountForAccountID:self.accountID];
        self.accountID = nil;
    }
    MonalWireResetDataStore(self.dataDir);
}

- (BOOL)connectWithTimeout:(NSTimeInterval)timeout error:(NSError**)error {
    MonalWireLog("connect: begin");
    [HelperTools initSystem];
    MonalWireEnsurePlaintextHooks();

    [[MLNotificationQueue currentQueue] addObserver:self
                                         selector:@selector(handleNewMessage:)
                                             name:kMonalNewMessageNotice
                                           object:nil];
    [[NSNotificationCenter defaultCenter] addObserver:self
                                           selector:@selector(handleNewMessage:)
                                               name:kMonalNewMessageNotice
                                             object:nil];

    for (int attempt = 1; attempt <= 3; attempt++) {
        if (attempt > 1) {
            MonalWireLog("connect: retry after failure");
            [self resetAccountForRetry];
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:8.0]];
            MonalWireEnsurePlaintextHooks();
        }
        if (![self startAccountLogin]) {
            if (error) {
                *error = [NSError errorWithDomain:@"MonalWire" code:1 userInfo:@{NSLocalizedDescriptionKey: @"login failed"}];
            }
            return NO;
        }
        if ([self waitForSessionWithTimeout:timeout error:error]) {
            return YES;
        }
    }
    return NO;
}

- (void)triggerSmacksFallbackIfNeeded:(xmpp*)acc {
    if (!acc || acc.accountState != kStateBound || self.smacksFallbackScheduled) {
        return;
    }
    self.smacksFallbackScheduled = YES;
    MonalWireLog("connect: scheduling smacks/init fallback after bind");
    xmpp* account = acc;
    MonalWireDispatchOnReceiveQueue(account, ^{
        if (account.connectionProperties.supportsSM3) {
            MonalWireLog("connect: sending smacks enable after bind");
            MLXMLNode* enable = [[MLXMLNode alloc]
                initWithElement:@"enable"
                andNamespace:@"urn:xmpp:sm:3"
                withAttributes:@{@"resume": @"true"}
                andChildren:@[]
                andData:nil];
            [account send:enable];
        } else {
            MonalWireLog("connect: initSession after bind (no smacks)");
            [account initSession];
        }
    });
}

- (void)triggerLegacyBindIfNeeded:(xmpp*)acc {
    if (!acc || acc.accountState != kStateLoggedIn || self.legacyBindTriggered) {
        if (acc && acc.accountState != kStateLoggedIn) {
            self.loggedInSince = nil;
        }
        return;
    }
    if (!self.loggedInSince) {
        self.loggedInSince = [NSDate date];
        return;
    }
    // Wait for ejabberd post-auth stream features before forcing legacy bind.
    if ([self.loggedInSince timeIntervalSinceNow] > -8.0) {
        return;
    }
    self.legacyBindTriggered = YES;
    MonalWireTriggerLegacyBindAfterSasl2(acc);
}

- (BOOL)waitForSessionWithTimeout:(NSTimeInterval)timeout error:(NSError**)error {
    self.smacksFallbackScheduled = NO;
    self.legacyBindTriggered = NO;
    self.loggedInSince = nil;
    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    NSDate* lastHeartbeat = [NSDate date];
    xmpp* acc = nil;
    int lastLoggedState = -100;
    while ([deadline timeIntervalSinceNow] > 0) {
        acc = [self account];
        int state = acc ? (int)acc.accountState : -99;
        if (state != lastLoggedState) {
            char buf[64];
            snprintf(buf, sizeof(buf), "connect state=%d", state);
            MonalWireLog(buf);
            if (state == kStateDisconnected) {
                MonalWireLog("connect: disconnected (reconnecting?)");
            } else if (state == kStateLoggedOut) {
                MonalWireLog("connect: logged out");
            } else if (state == kStateBinding) {
                MonalWireLog("connect: binding resource");
            } else if (state == kStateBound) {
                MonalWireLog("connect: bound, waiting for smacks/init");
            } else if (state >= kStateInitStarted) {
                MonalWireLog("connect: session init started");
            }
            lastLoggedState = state;
        }
        if ([lastHeartbeat timeIntervalSinceNow] < -30.0) {
            char buf[64];
            snprintf(buf, sizeof(buf), "connect: still waiting state=%d", state);
            MonalWireLog(buf);
            lastHeartbeat = [NSDate date];
        }
        if (acc && acc.accountState < kStateHasStream) {
            MonalWireForcePlaintextStreamReady(acc);
        }
        [self triggerLegacyBindIfNeeded:acc];
        [self triggerSmacksFallbackIfNeeded:acc];
        if (acc && acc.accountState >= kStateInitStarted) {
            MonalWireLog("connect: init started");
            return YES;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    }
    acc = [self account];
    if (!acc || acc.accountState < kStateInitStarted) {
        if (error) {
            int state = acc ? (int)acc.accountState : -99;
            *error = [NSError errorWithDomain:@"MonalWire" code:2 userInfo:@{
                NSLocalizedDescriptionKey: [NSString stringWithFormat:@"timeout waiting for XMPP session (state=%d)", state],
            }];
        }
        return NO;
    }
    return YES;
}

static void wireQueryOmemoDevices(xmpp* acc, NSString* jid, BOOL subscribe) {
    SEL sel = NSSelectorFromString(@"queryOMEMODevices:withSubscribe:");
    if ([acc.omemo respondsToSelector:sel]) {
        ((void (*)(id, SEL, NSString*, BOOL))objc_msgSend)(acc.omemo, sel, jid, subscribe);
    }
}

static void wireForceOmemoPublish(xmpp* acc, NSString* ownJid) {
    SEL processSel = NSSelectorFromString(@"processOMEMODevices:from:");
    if ([acc.omemo respondsToSelector:processSel]) {
        ((void (*)(id, SEL, NSSet*, NSString*))objc_msgSend)(acc.omemo, processSel, [NSSet set], ownJid);
    }
    SEL keysSel = NSSelectorFromString(@"generateNewKeysIfNeeded");
    if ([acc.omemo respondsToSelector:keysSel]) {
        ((BOOL (*)(id, SEL))objc_msgSend)(acc.omemo, keysSel);
    }
    SEL bundleSel = NSSelectorFromString(@"sendOMEMOBundle");
    if ([acc.omemo respondsToSelector:bundleSel]) {
        ((void (*)(id, SEL))objc_msgSend)(acc.omemo, bundleSel);
    }
    SEL publishSel = NSSelectorFromString(@"publishOwnDeviceList");
    if ([acc.omemo respondsToSelector:publishSel]) {
        ((void (*)(id, SEL))objc_msgSend)(acc.omemo, publishSel);
    }
}

- (BOOL)ownDeviceListedOnOmemo:(xmpp*)acc {
    if (!acc || !acc.omemo) {
        return NO;
    }
    NSNumber* deviceId = [acc.omemo getDeviceId];
    if (deviceId == nil) {
        return NO;
    }
    NSSet* ownList = nil;
    @try {
        ownList = [acc.omemo valueForKey:@"ownDeviceList"];
    } @catch (NSException* e) {
        (void)e;
        return NO;
    }
    return ownList != nil && [ownList containsObject:deviceId];
}

- (BOOL)waitForOmemoReadyWithTimeout:(NSTimeInterval)timeout error:(NSError**)error {
    MonalWireLog("waitForOmemoReady: begin");
    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    BOOL fetchTriggered = NO;
    BOOL forcePublishTriggered = NO;
    NSDate* fetchStartedAt = nil;
    int lastLogPhase = -1;
    while ([deadline timeIntervalSinceNow] > 0) {
        xmpp* acc = [self account];
        if (!acc || !acc.omemo) {
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
            continue;
        }
        NSString* ownJid = acc.connectionProperties.identity.jid;
        BOOL sessionReady = acc.accountState >= kStateCatchupDone;
        BOOL omemoCatchup = acc.omemo.state.catchupDone;
        BOOL listed = [self ownDeviceListedOnOmemo:acc];
        BOOL bundlesIdle = acc.omemo.openBundleFetchCnt == 0;
        int phase = (sessionReady ? 4 : 0) + (omemoCatchup ? 2 : 0) + (listed ? 1 : 0);
        if (phase != lastLogPhase) {
            char buf[96];
            snprintf(buf, sizeof(buf), "waitForOmemoReady: session=%d omemoCatchup=%d listed=%d bundles=%lu",
                     sessionReady, omemoCatchup, listed, acc.omemo.openBundleFetchCnt);
            MonalWireLog(buf);
            lastLogPhase = phase;
        }
        if (sessionReady && omemoCatchup && listed && bundlesIdle) {
            MonalWireLog("waitForOmemoReady: ready");
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:3.0]];
            return YES;
        }
        if (sessionReady && omemoCatchup && !fetchTriggered) {
            fetchTriggered = YES;
            fetchStartedAt = [NSDate date];
            MonalWireLog("waitForOmemoReady: fetching own devicelist");
            wireQueryOmemoDevices(acc, ownJid, NO);
        }
        if (sessionReady && omemoCatchup && fetchTriggered && !listed && !forcePublishTriggered
            && fetchStartedAt && [fetchStartedAt timeIntervalSinceNow] < -10.0) {
            forcePublishTriggered = YES;
            MonalWireLog("waitForOmemoReady: forcing OMEMO publish");
            wireForceOmemoPublish(acc, ownJid);
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    }
    if (error) {
        xmpp* acc = [self account];
        *error = [NSError errorWithDomain:@"MonalWire" code:5 userInfo:@{
            NSLocalizedDescriptionKey: [NSString stringWithFormat:
                @"timeout waiting for OMEMO publish (listed=%d bundles=%lu state=%d)",
                [self ownDeviceListedOnOmemo:acc],
                acc ? acc.omemo.openBundleFetchCnt : 0UL,
                acc ? (int)acc.accountState : -99],
        }];
    }
    return NO;
}

- (BOOL)preparePeer:(NSString*)peerJid error:(NSError**)error {
    MonalWireLog([[NSString stringWithFormat:@"preparePeer: %@", peerJid] UTF8String]);
    self.preparedPeerJid = peerJid;
    xmpp* acc = [self account];
    if (!acc) {
        if (error) {
            *error = [NSError errorWithDomain:@"MonalWire" code:4 userInfo:@{NSLocalizedDescriptionKey: @"not connected"}];
        }
        return NO;
    }
    MLContact* contact = [MLContact createContactFromJid:peerJid andAccountID:self.accountID];
    [[MLXMPPManager sharedInstance] addContact:contact];
    [[DataLayer sharedInstance] addContact:peerJid forAccount:self.accountID nickname:nil];
    [[DataLayer sharedInstance] setSubscription:kSubBoth andAsk:@"" forContact:peerJid andAccount:self.accountID];
    MonalWireLog([[NSString stringWithFormat:@"preparePeer: subscribed %@ both ways", peerJid] UTF8String]);
    if (acc.omemo) {
        [acc.omemo subscribeAndFetchDevicelistIfNoSessionExistsForJid:peerJid];
    }
    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:60];
    while ([deadline timeIntervalSinceNow] > 0) {
        if (acc.accountState >= kStateCatchupDone) {
            break;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.5]];
    }
    deadline = [NSDate dateWithTimeIntervalSinceNow:45];
    while ([deadline timeIntervalSinceNow] > 0) {
        if (!acc.omemo || acc.omemo.openBundleFetchCnt == 0) {
            break;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    }
    if (acc.omemo && acc.omemo.openBundleFetchCnt > 0) {
        MonalWireLog([[NSString stringWithFormat:@"preparePeer: bundle fetches still open (%lu)",
                       acc.omemo.openBundleFetchCnt] UTF8String]);
    }
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:2.0]];
    return YES;
}

- (BOOL)sendEncrypted:(NSString*)peerJid body:(NSString*)body error:(NSError**)error {
    MonalWireLog([[NSString stringWithFormat:@"sendEncrypted: peer=%@ body=%@", peerJid, body] UTF8String]);
    if (![self preparePeer:peerJid error:error]) {
        return NO;
    }
    xmpp* acc = [self account];
    MLContact* contact = [MLContact createContactFromJid:peerJid andAccountID:self.accountID];
    NSString* messageId = [[NSUUID UUID] UUIDString];
    [acc sendMessage:body toContact:contact isEncrypted:YES isUpload:NO andMessageId:messageId];
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:1.0]];
    return YES;
}

- (void)noteBodyIfMatching:(NSString*)body expected:(NSString*)expected {
    if (body.length && [body isEqualToString:expected]) {
        self.lastBody = body;
    }
}

- (NSString*)latestBodyFromDataLayerForPeer:(NSString*)peerJid {
    if (!peerJid || !self.accountID) {
        return nil;
    }
    MLMessage* msg = [[DataLayer sharedInstance] lastMessageForContact:peerJid forAccount:self.accountID];
    return msg.messageText;
}

- (BOOL)awaitBody:(NSString*)expected timeout:(NSTimeInterval)timeout {
    MonalWireLog([[NSString stringWithFormat:@"awaitBody: expect=%@", expected] UTF8String]);
    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    NSDate* lastPeerRefresh = [NSDate date];
    while ([deadline timeIntervalSinceNow] > 0) {
        if (self.preparedPeerJid && [lastPeerRefresh timeIntervalSinceNow] < -10.0) {
            xmpp* acc = [self account];
            if (acc.omemo) {
                [acc.omemo subscribeAndFetchDevicelistIfNoSessionExistsForJid:self.preparedPeerJid];
            }
            lastPeerRefresh = [NSDate date];
        }
        if (self.preparedPeerJid) {
            NSString* dbBody = [self latestBodyFromDataLayerForPeer:self.preparedPeerJid];
            if (dbBody.length) {
                MonalWireLog([[NSString stringWithFormat:@"awaitBody: db body=%@", dbBody] UTF8String]);
                [self noteBodyIfMatching:dbBody expected:expected];
            }
        }
        if ([self.lastBody isEqualToString:expected]) {
            return YES;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    }
    if (self.preparedPeerJid) {
        NSString* dbBody = [self latestBodyFromDataLayerForPeer:self.preparedPeerJid];
        [self noteBodyIfMatching:dbBody expected:expected];
    }
    return [self.lastBody isEqualToString:expected];
}

- (void)disconnect {
    if (self.accountID != nil) {
        [[MLXMPPManager sharedInstance] disconnectAccount:self.accountID withExplicitLogout:YES];
    }
    [[MLNotificationQueue currentQueue] removeObserver:self];
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
