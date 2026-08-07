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
@property(nonatomic, assign) int streamStartNudgeCount;
@property(nonatomic, strong) NSDate* loggedInSince;
@property(nonatomic, strong) NSDate* connectedSince;
@property(nonatomic, strong) NSDate* hasStreamSince;
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
    if ([message.messageText hasPrefix:@"Could not decrypt"]
        || [message.messageText hasPrefix:@"OMEMO:"]) {
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
    [self nudgeAccountConnectIfNeeded];
    return YES;
}

- (void)nudgeAccountConnectIfNeeded {
    if (self.accountID == nil) {
        return;
    }
    xmpp* acc = [self account];
    if (!acc) {
        MonalWireLog("connect: nudging connectAccount (no xmpp yet)");
        [[MLXMPPManager sharedInstance] connectAccount:self.accountID];
        return;
    }
    if (acc.accountState <= kStateLoggedOut) {
        MonalWireLog("connect: nudging xmpp connect from logged out");
        [acc connect];
    }
}

- (void)resetAccountForRetry {
    NSNumber* oldId = self.accountID;
    if (oldId != nil) {
        [[MLXMPPManager sharedInstance] disconnectAccount:oldId withExplicitLogout:YES];
        [[MLXMPPManager sharedInstance] removeAccountForAccountID:oldId];
        self.accountID = nil;
    }
    MonalWireResetDataStore(self.dataDir);
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:5.0]];
    MonalWireEnsurePlaintextHooks();
}

- (void)cycleDisconnectConnect:(xmpp*)acc {
    if (!acc) {
        [self nudgeAccountConnectIfNeeded];
        return;
    }
    MonalWireLog("connect: cycling disconnect/connect");
    [acc disconnect:NO];
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:3.0]];
    MonalWireClearStreamFeatureCache(acc);
    MonalWireEnsurePlaintextHooks();
    [acc connect];
}

- (void)nudgeSessionProgress:(xmpp*)acc {
    if (!acc) {
        return;
    }
    MonalWireLog("connect: nudging session progress (bind/smacks)");
    MonalWireEnsurePlaintextHooks();
    MonalWireClearStreamFeatureCache(acc);
    [self triggerLegacyBindIfNeeded:acc];
    [self triggerSmacksFallbackIfNeeded:acc];
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:15.0]];
}

- (BOOL)recoverConnectAttempt:(xmpp*)acc phase:(int)phase nextPhase:(int*)nextPhase {
    int state = acc ? (int)acc.accountState : -99;
    if (phase == 0) {
        if (acc && state == kStateConnected) {
            MonalWireLog("connect: recovery phase 0 stream nudge");
            MonalWireNudgeStreamStart(acc);
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:10.0]];
        } else if (acc && state >= kStateHasStream && state < kStateInitStarted) {
            MonalWireLog("connect: recovery phase 0 session nudge");
            [self nudgeSessionProgress:acc];
        } else {
            MonalWireLog("connect: recovery phase 0 disconnect/connect");
            [self cycleDisconnectConnect:acc];
        }
        *nextPhase = 1;
        return NO;
    }
    if (phase == 1) {
        if (acc && state >= kStateHasStream && state < kStateInitStarted) {
            MonalWireLog("connect: recovery phase 1 session nudge");
            [self nudgeSessionProgress:acc];
            *nextPhase = 2;
            return NO;
        }
        MonalWireLog("connect: recovery phase 1 disconnect/connect");
        [self cycleDisconnectConnect:acc];
        *nextPhase = 2;
        return NO;
    }
    if (acc && state >= kStateHasStream) {
        MonalWireLog("connect: recovery phase 2 session nudge (skip reset)");
        [self nudgeSessionProgress:acc];
        *nextPhase = 0;
        return NO;
    }
    MonalWireLog("connect: recovery phase 2 full reset");
    [self resetAccountForRetry];
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:10.0]];
    *nextPhase = 0;
    return YES;
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

    if (![self startAccountLogin]) {
        if (error) {
            *error = [NSError errorWithDomain:@"MonalWire" code:1 userInfo:@{NSLocalizedDescriptionKey: @"login failed"}];
        }
        return NO;
    }

    NSDate* overallDeadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    int recoveryPhase = 0;
    while ([overallDeadline timeIntervalSinceNow] > 0) {
        NSTimeInterval slice = MIN(90.0, [overallDeadline timeIntervalSinceNow]);
        if (slice <= 0) {
            break;
        }
        if ([self waitForSessionWithTimeout:slice error:error]) {
            return YES;
        }

        xmpp* acc = [self account];
        BOOL needsLogin = [self recoverConnectAttempt:acc phase:recoveryPhase nextPhase:&recoveryPhase];
        if (needsLogin && ![self startAccountLogin]) {
            if (error) {
                *error = [NSError errorWithDomain:@"MonalWire" code:1 userInfo:@{NSLocalizedDescriptionKey: @"login failed after reset"}];
            }
            return NO;
        }
        MonalWireEnsurePlaintextHooks();
    }

    if (error && !*error) {
        xmpp* acc = [self account];
        int state = acc ? (int)acc.accountState : -99;
        *error = [NSError errorWithDomain:@"MonalWire" code:2 userInfo:@{
            NSLocalizedDescriptionKey: [NSString stringWithFormat:@"timeout waiting for XMPP session (state=%d)", state],
        }];
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
    self.connectedSince = nil;
    self.hasStreamSince = nil;
    self.streamStartNudgeCount = 0;
    self.loggedInSince = nil;
    self.connectedSince = nil;
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
        if (acc && acc.accountState == kStateConnected) {
            if (!self.connectedSince) {
                self.connectedSince = [NSDate date];
            } else if (self.streamStartNudgeCount < 3
                       && [self.connectedSince timeIntervalSinceNow] < -(5.0 + self.streamStartNudgeCount * 10.0)) {
                self.streamStartNudgeCount++;
                MonalWireNudgeStreamStart(acc);
            }
        } else {
            self.connectedSince = nil;
            self.streamStartNudgeCount = 0;
        }
        if (acc && acc.accountState >= kStateHasStream && acc.accountState < kStateInitStarted) {
            if (!self.hasStreamSince) {
                self.hasStreamSince = [NSDate date];
            } else if ([self.hasStreamSince timeIntervalSinceNow] < -15.0) {
                MonalWireLog("connect: nudging mid-auth progress");
                [self nudgeSessionProgress:acc];
                self.hasStreamSince = [NSDate date];
            }
        } else {
            self.hasStreamSince = nil;
        }
        if (acc && (acc.accountState == kStateDisconnected || acc.accountState == kStateLoggedOut)) {
            [self nudgeAccountConnectIfNeeded];
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

static id wireMakeSignalAddress(NSString* jid, uint32_t deviceId) {
    Class cls = NSClassFromString(@"SignalAddress");
    if (!cls) {
        return nil;
    }
    id addr = [cls alloc];
    SEL initSel = NSSelectorFromString(@"initWithName:deviceId:");
    return ((id (*)(id, SEL, NSString*, uint32_t))objc_msgSend)(addr, initSel, jid, deviceId);
}

static BOOL wirePeerOmemoDevicesReady(xmpp* acc, NSString* peerJid) {
    if (!acc || !acc.omemo || !peerJid.length) {
        return NO;
    }
    NSSet<NSNumber*>* devices = [acc.omemo knownDevicesForAddressName:peerJid];
    if (devices.count == 0) {
        return NO;
    }
    for (NSNumber* deviceId in devices) {
        id address = wireMakeSignalAddress(peerJid, deviceId.unsignedIntValue);
        if (!address) {
            return NO;
        }
        NSData* identity = [acc.omemo getIdentityForAddress:address];
        if (!identity.length) {
            return NO;
        }
    }
    return YES;
}

static void wireFetchPeerBundle(xmpp* acc, NSString* jid, NSNumber* deviceId) {
    SEL sel = NSSelectorFromString(@"queryOMEMOBundleFrom:andDevice:");
    if ([acc.omemo respondsToSelector:sel]) {
        ((void (*)(id, SEL, NSString*, NSNumber*))objc_msgSend)(acc.omemo, sel, jid, deviceId);
    }
}

static void wireTrustPeerDeviceId(xmpp* acc, NSString* peerJid, uint32_t deviceId) {
    id address = wireMakeSignalAddress(peerJid, deviceId);
    if (address) {
        [acc.omemo updateTrust:YES forAddress:address];
    }
}

static void wireTrustAllKnownPeerDevices(xmpp* acc, NSString* peerJid) {
    if (!acc || !acc.omemo || !peerJid.length) {
        return;
    }
    for (NSNumber* deviceId in [acc.omemo knownDevicesForAddressName:peerJid]) {
        id address = wireMakeSignalAddress(peerJid, deviceId.unsignedIntValue);
        if (address) {
            [acc.omemo updateTrust:YES forAddress:address];
        }
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
        wireQueryOmemoDevices(acc, peerJid, YES);
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
    deadline = [NSDate dateWithTimeIntervalSinceNow:15];
    BOOL peerDevicesReady = NO;
    while ([deadline timeIntervalSinceNow] > 0) {
        if (wirePeerOmemoDevicesReady(acc, peerJid)) {
            wireTrustAllKnownPeerDevices(acc, peerJid);
            peerDevicesReady = YES;
            MonalWireLog([[NSString stringWithFormat:@"preparePeer: trusted %lu OMEMO device(s) for %@",
                           (unsigned long)[acc.omemo knownDevicesForAddressName:peerJid].count,
                           peerJid] UTF8String]);
            break;
        }
        if (acc.omemo) {
            wireQueryOmemoDevices(acc, peerJid, NO);
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.5]];
    }
    if (!peerDevicesReady) {
        MonalWireLog([[NSString stringWithFormat:@"preparePeer: peer OMEMO devices not ready for %@ (known=%lu)",
                       peerJid,
                       acc.omemo ? (unsigned long)[acc.omemo knownDevicesForAddressName:peerJid].count : 0UL] UTF8String]);
    }
    if (acc.omemo && acc.omemo.openBundleFetchCnt > 0) {
        MonalWireLog([[NSString stringWithFormat:@"preparePeer: bundle fetches still open (%lu)",
                       acc.omemo.openBundleFetchCnt] UTF8String]);
    }
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:2.0]];
    return YES;
}

- (BOOL)waitForPeerOmemoReadyWithTimeout:(NSTimeInterval)timeout error:(NSError**)error {
    if (!self.preparedPeerJid.length) {
        if (error) {
            *error = [NSError errorWithDomain:@"MonalWire" code:6 userInfo:@{
                NSLocalizedDescriptionKey: @"waitForPeerOmemoReady requires preparedPeerJid",
            }];
        }
        return NO;
    }
    NSString* peerJid = self.preparedPeerJid;
    MonalWireLog([[NSString stringWithFormat:@"waitForPeerOmemoReady: %@", peerJid] UTF8String]);
    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    NSUInteger lastKnown = 0;
    while ([deadline timeIntervalSinceNow] > 0) {
        xmpp* acc = [self account];
        if (acc.omemo) {
            wireQueryOmemoDevices(acc, peerJid, YES);
            [acc.omemo subscribeAndFetchDevicelistIfNoSessionExistsForJid:peerJid];
        }
        NSDate* bundleDeadline = [NSDate dateWithTimeIntervalSinceNow:5];
        while ([bundleDeadline timeIntervalSinceNow] > 0) {
            if (!acc.omemo || acc.omemo.openBundleFetchCnt == 0) {
                break;
            }
            [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
        }
        NSUInteger known = acc.omemo ? [acc.omemo knownDevicesForAddressName:peerJid].count : 0;
        if (known != lastKnown) {
            MonalWireLog([[NSString stringWithFormat:@"waitForPeerOmemoReady: known=%lu for %@",
                           (unsigned long)known, peerJid] UTF8String]);
            lastKnown = known;
        }
        if (wirePeerOmemoDevicesReady(acc, peerJid)) {
            wireTrustAllKnownPeerDevices(acc, peerJid);
            MonalWireLog([[NSString stringWithFormat:@"waitForPeerOmemoReady: ready (%lu device(s))",
                           (unsigned long)known] UTF8String]);
            return YES;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.5]];
    }
    xmpp* acc = [self account];
    NSUInteger known = acc.omemo ? [acc.omemo knownDevicesForAddressName:peerJid].count : 0;
    MonalWireLog([[NSString stringWithFormat:@"waitForPeerOmemoReady: timeout (known=%lu)",
                   (unsigned long)known] UTF8String]);
    if (error) {
        *error = [NSError errorWithDomain:@"MonalWire" code:7 userInfo:@{
            NSLocalizedDescriptionKey: [NSString stringWithFormat:
                @"timeout waiting for peer OMEMO devices for %@ (known=%lu)", peerJid, (unsigned long)known],
        }];
    }
    return NO;
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
    if (!body.length || [body hasPrefix:@"Could not decrypt"] || [body hasPrefix:@"OMEMO:"]) {
        return;
    }
    if ([body isEqualToString:expected]) {
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
        if (self.preparedPeerJid && [lastPeerRefresh timeIntervalSinceNow] < -2.0) {
            xmpp* acc = [self account];
            if (acc.omemo) {
                wireQueryOmemoDevices(acc, self.preparedPeerJid, YES);
                [acc.omemo subscribeAndFetchDevicelistIfNoSessionExistsForJid:self.preparedPeerJid];
                for (NSNumber* deviceId in [acc.omemo knownDevicesForAddressName:self.preparedPeerJid]) {
                    wireFetchPeerBundle(acc, self.preparedPeerJid, deviceId);
                }
                wireTrustAllKnownPeerDevices(acc, self.preparedPeerJid);
            }
            lastPeerRefresh = [NSDate date];
        }
        if (self.preparedPeerJid) {
            NSString* dbBody = [self latestBodyFromDataLayerForPeer:self.preparedPeerJid];
            if ([dbBody hasPrefix:@"Could not decrypt"]) {
                MonalWireLog([[NSString stringWithFormat:@"awaitBody: decrypt error=%@", dbBody] UTF8String]);
                xmpp* acc = [self account];
                if (acc.omemo) {
                    for (NSNumber* deviceId in [acc.omemo knownDevicesForAddressName:self.preparedPeerJid]) {
                        wireFetchPeerBundle(acc, self.preparedPeerJid, deviceId);
                        wireTrustPeerDeviceId(acc, self.preparedPeerJid, deviceId.unsignedIntValue);
                    }
                }
            }
            if ([dbBody hasPrefix:@"Could not decrypt because you didn't trust the sender's device "]) {
                unsigned int deviceId = 0;
                NSString* prefix = @"Could not decrypt because you didn't trust the sender's device ";
                if ([dbBody hasPrefix:prefix]) {
                    NSString* tail = [dbBody substringFromIndex:prefix.length];
                    deviceId = (unsigned int)[tail intValue];
                }
                if (deviceId > 0) {
                    xmpp* acc = [self account];
                    if (acc.omemo) {
                        wireFetchPeerBundle(acc, self.preparedPeerJid, @(deviceId));
                        wireTrustPeerDeviceId(acc, self.preparedPeerJid, deviceId);
                    }
                }
            }
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
