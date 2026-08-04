#import "WireBootstrap.h"
#import <objc/runtime.h>
#import <objc/message.h>
#import <SAMKeychain/SAMKeychain.h>
#import <monalxmpp/HelperTools.h>
#import <monalxmpp/MLProcessLock.h>
#import <monalxmpp/MLConstants.h>
#import <monalxmpp/xmpp.h>
#import <Network/Network.h>
static NSMutableSet<NSNumber*>* wireSasl2RestartedAccounts = nil;
static NSMutableDictionary<NSString*, NSString*>* wireKeychainPasswords = nil;

static NSString* wireKeychainKey(NSString* service, NSString* account) {
    return [NSString stringWithFormat:@"%@::%@", service ?: @"", account ?: @""];
}

static void installWireKeychainShim(void) {
    Class sam = [SAMKeychain class];
    if (!sam) {
        return;
    }
    wireKeychainPasswords = [NSMutableDictionary new];

    Method setPw = class_getClassMethod(sam, @selector(setPassword:forService:account:));
    if (setPw) {
        class_replaceMethod(object_getClass(sam), @selector(setPassword:forService:account:),
            imp_implementationWithBlock(^BOOL(id _Nonnull cls, NSString* password, NSString* service, NSString* account) {
                wireKeychainPasswords[wireKeychainKey(service, account)] = password;
                return YES;
            }), method_getTypeEncoding(setPw));
    }

    Method setPwErr = class_getClassMethod(sam, @selector(setPassword:forService:account:error:));
    if (setPwErr) {
        class_replaceMethod(object_getClass(sam), @selector(setPassword:forService:account:error:),
            imp_implementationWithBlock(^BOOL(id _Nonnull cls, NSString* password, NSString* service, NSString* account, NSError** error) {
                wireKeychainPasswords[wireKeychainKey(service, account)] = password;
                if (error) {
                    *error = nil;
                }
                return YES;
            }), method_getTypeEncoding(setPwErr));
    }

    Method getPw = class_getClassMethod(sam, @selector(passwordForService:account:));
    if (getPw) {
        class_replaceMethod(object_getClass(sam), @selector(passwordForService:account:),
            imp_implementationWithBlock(^NSString*(id _Nonnull cls, NSString* service, NSString* account) {
                return wireKeychainPasswords[wireKeychainKey(service, account)];
            }), method_getTypeEncoding(getPw));
    }

    Method getPwErr = class_getClassMethod(sam, @selector(passwordForService:account:error:));
    if (getPwErr) {
        class_replaceMethod(object_getClass(sam), @selector(passwordForService:account:error:),
            imp_implementationWithBlock(^NSString*(id _Nonnull cls, NSString* service, NSString* account, NSError** error) {
                NSString* password = wireKeychainPasswords[wireKeychainKey(service, account)];
                if (error) {
                    *error = nil;
                }
                return password;
            }), method_getTypeEncoding(getPwErr));
    }

    Method setAccess = class_getClassMethod(sam, @selector(setAccessibilityType:));
    if (setAccess) {
        class_replaceMethod(object_getClass(sam), @selector(setAccessibilityType:),
            imp_implementationWithBlock(^(id _Nonnull cls, CFTypeRef accessibility) {
                (void)cls;
                (void)accessibility;
            }), method_getTypeEncoding(setAccess));
    }

    Method delPw = class_getClassMethod(sam, @selector(deletePasswordForService:account:));
    if (delPw) {
        class_replaceMethod(object_getClass(sam), @selector(deletePasswordForService:account:),
            imp_implementationWithBlock(^BOOL(id _Nonnull cls, NSString* service, NSString* account) {
                (void)cls;
                [wireKeychainPasswords removeObjectForKey:wireKeychainKey(service, account)];
                return YES;
            }), method_getTypeEncoding(delPw));
    }
}

typedef void (*WireStartXmppStreamIMP)(xmpp* self, SEL _cmd, BOOL withXMLOpening, BOOL withStartTLS, BOOL directWrite);
static WireStartXmppStreamIMP wireOrigStartXmppStream = NULL;

static void installWirePlaintextMlStream(void);

static void wireSetStartTLSComplete(xmpp* account, BOOL value) {
    Ivar tlsIvar = class_getInstanceVariable([xmpp class], "_startTLSComplete");
    if (!tlsIvar) {
        fprintf(stderr, "MonalWire: _startTLSComplete ivar missing\n");
        fflush(stderr);
        return;
    }
    ptrdiff_t offset = ivar_getOffset(tlsIvar);
    void* rawSelf = (__bridge void*)account;
    *(BOOL*)((uintptr_t)rawSelf + offset) = value;
}

static void wireStartXmppStream(xmpp* self, SEL _cmd, BOOL withXMLOpening, BOOL withStartTLS, BOOL directWrite) {
    (void)withStartTLS;
    (void)directWrite;
    // Plaintext interop: skip STARTTLS but treat stream features as post-TLS (xmpp.m ~3170).
    wireSetStartTLSComplete(self, YES);
    // Keep Monal's directWrite pipelining so the stream header is sent before TCP open completes.
    wireOrigStartXmppStream(self, _cmd, withXMLOpening, NO, YES);
}

typedef void (*WireProcessInputIMP)(xmpp* self, SEL _cmd, id parsedStanza, BOOL delayedReplay);
static WireProcessInputIMP wireOrigProcessInput = NULL;

static void wireMaybeRestartStreamAfterSasl2(xmpp* account, id parsedStanza) {
    (void)parsedStanza;
    MonalWireRestartStreamAfterSasl2Login(account);
}

void MonalWireRestartStreamAfterSasl2Login(xmpp* account) {
    if (!account || account.accountState != kStateLoggedIn) {
        return;
    }
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        wireSasl2RestartedAccounts = [NSMutableSet new];
    });
    NSNumber* accountID = account.accountID;
    if (!accountID || [wireSasl2RestartedAccounts containsObject:accountID]) {
        return;
    }
    [wireSasl2RestartedAccounts addObject:accountID];

    fprintf(stderr, "MonalWire: SASL2 logged in without session — restarting stream for bind\n");
    fflush(stderr);

    SEL prepareParser = NSSelectorFromString(@"prepareXMPPParser");
    if ([account respondsToSelector:prepareParser]) {
        ((void (*)(id, SEL))objc_msgSend)(account, prepareParser);
    }
    if (wireOrigStartXmppStream) {
        wireSetStartTLSComplete(account, YES);
        wireOrigStartXmppStream(
            account,
            NSSelectorFromString(@"startXMPPStreamWithXMLOpening:withStartTLS:andDirectWrite:"),
            YES,
            NO,
            YES);
    } else {
        SEL streamSel = NSSelectorFromString(@"startXMPPStreamWithXMLOpening:");
        if ([account respondsToSelector:streamSel]) {
            ((void (*)(id, SEL, BOOL))objc_msgSend)(account, streamSel, YES);
        }
    }
}

static void wireProcessInput(xmpp* self, SEL _cmd, id parsedStanza, BOOL delayedReplay) {
    if (!self.connectionProperties.server.isDirectTLS) {
        SEL checkSel = NSSelectorFromString(@"check:");
        if ([parsedStanza respondsToSelector:checkSel]) {
            BOOL isFeatures = ((BOOL (*)(id, SEL, NSString*))objc_msgSend)(
                parsedStanza, checkSel, @"/{http://etherx.jabber.org/streams}features");
            if (isFeatures) {
                wireSetStartTLSComplete(self, YES);
            }
        }
    }
    wireOrigProcessInput(self, _cmd, parsedStanza, delayedReplay);
    wireMaybeRestartStreamAfterSasl2(self, parsedStanza);
}

static void installWirePlaintextProcessInput(void) {
    Class cls = [xmpp class];
    SEL sel = NSSelectorFromString(@"processInput:withDelayedReplay:");
    Method method = class_getInstanceMethod(cls, sel);
    if (!method || wireOrigProcessInput) {
        return;
    }
    wireOrigProcessInput = (WireProcessInputIMP)method_getImplementation(method);
    method_setImplementation(method, (IMP)wireProcessInput);
}

static void installWirePlaintextXmppStream(void) {
    Class cls = [xmpp class];
    SEL sel = NSSelectorFromString(@"startXMPPStreamWithXMLOpening:withStartTLS:andDirectWrite:");
    Method method = class_getInstanceMethod(cls, sel);
    if (!method || wireOrigStartXmppStream) {
        return;
    }
    wireOrigStartXmppStream = (WireStartXmppStreamIMP)method_getImplementation(method);
    method_setImplementation(method, (IMP)wireStartXmppStream);
    installWirePlaintextProcessInput();
    installWirePlaintextMlStream();
    fprintf(stderr, "MonalWire: plaintext XMPP stream hook installed\n");
    fflush(stderr);
}

static void wireStubMlStreamMethod(Class cls, SEL sel, IMP imp) {
    Method method = class_getInstanceMethod(cls, sel);
    if (method) {
        method_setImplementation(method, imp);
    }
}

static void installWirePlaintextMlStream(void) {
    static BOOL mlStreamHookInstalled = NO;
    if (mlStreamHookInstalled) {
        return;
    }
    Class cls = NSClassFromString(@"MLStream");
    if (!cls) {
        return;
    }
    int stubCount = 0;
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"tlsVersion"),
        imp_implementationWithBlock(^uint16_t(id _Nonnull stream) {
            (void)stream;
            return tls_protocol_version_TLSv12;
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"tlsVersion"))) {
        stubCount++;
    }
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"isTLS13"),
        imp_implementationWithBlock(^BOOL(id _Nonnull stream) {
            (void)stream;
            return NO;
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"isTLS13"))) {
        stubCount++;
    }
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"isTLS12"),
        imp_implementationWithBlock(^BOOL(id _Nonnull stream) {
            (void)stream;
            return YES;
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"isTLS12"))) {
        stubCount++;
    }
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"acceptedTlsEarlyData"),
        imp_implementationWithBlock(^BOOL(id _Nonnull stream) {
            (void)stream;
            return NO;
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"acceptedTlsEarlyData"))) {
        stubCount++;
    }
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"channelBindingDataForType:"),
        imp_implementationWithBlock(^NSData*(id _Nonnull stream, NSString* _Nullable type) {
            (void)stream;
            if (type != nil && [type isEqualToString:kServerDoesNotFollowXep0440Error]) {
                return [type dataUsingEncoding:NSUTF8StringEncoding];
            }
            return nil;
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"channelBindingDataForType:"))) {
        stubCount++;
    }
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"channelBindingData_TLSExporter"),
        imp_implementationWithBlock(^NSData*(id _Nonnull stream) {
            (void)stream;
            return nil;
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"channelBindingData_TLSExporter"))) {
        stubCount++;
    }
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"channelBindingData_TLSServerEndPoint"),
        imp_implementationWithBlock(^NSData*(id _Nonnull stream) {
            (void)stream;
            return nil;
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"channelBindingData_TLSServerEndPoint"))) {
        stubCount++;
    }
    wireStubMlStreamMethod(cls, NSSelectorFromString(@"supportedChannelBindingTypes"),
        imp_implementationWithBlock(^NSArray*(id _Nonnull stream) {
            (void)stream;
            // Plaintext interop: no TLS channel bindings (avoids SASL2 SCRAM abort at xmpp.m ~2742).
            return @[];
        }));
    if (class_getInstanceMethod(cls, NSSelectorFromString(@"supportedChannelBindingTypes"))) {
        stubCount++;
    }
    if (stubCount > 0) {
        mlStreamHookInstalled = YES;
        fprintf(stderr, "MonalWire: plaintext MLStream TLS hook installed (%d methods)\n", stubCount);
        fflush(stderr);
    }
}

@implementation NSObject (MonalWireHelperTools)

+ (NSURL*) monalWire_getContainerURLForPathComponents:(NSArray*) components {
    NSURL* base = wireDataDir;
    for (NSString* component in components) {
        base = [base URLByAppendingPathComponent:component];
    }
    return base;
}

@end

void MonalWireBootstrapInstall(NSURL* dataDir) {
    static BOOL installed = NO;
    if (installed) {
        return;
    }
    installed = YES;

    wireDataDir = dataDir;
    [dataDir setResourceValue:@YES forKey:NSURLIsExcludedFromBackupKey error:nil];
    NSError* err = nil;
    [[NSFileManager defaultManager] createDirectoryAtURL:dataDir withIntermediateDirectories:YES attributes:nil error:&err];
    if (err) {
        @throw [NSException exceptionWithName:@"MonalWireBootstrap" reason:err.localizedDescription userInfo:nil];
    }

    Class helper = [HelperTools class];
    Method orig = class_getClassMethod(helper, @selector(getContainerURLForPathComponents:));
    Method repl = class_getClassMethod([NSObject class], @selector(monalWire_getContainerURLForPathComponents:));
    if (orig && repl) {
        method_exchangeImplementations(orig, repl);
    }

    // Headless simulator CLI: real keychain often fails; keep passwords in-process.
    installWireKeychainShim();

    // Plaintext ejabberd interop: do not pipeline STARTTLS on stream open.
    installWirePlaintextXmppStream();

    [HelperTools signalResumption];

    // Headless wire: skip device-id migration that reads keychain (Rust panic in simulator CLI).
    [[HelperTools defaultsDB] setBool:YES forKey:@"isSandboxAPNS"];
    [[HelperTools defaultsDB] setBool:NO forKey:@"udpLoggerEnabled"];
    [[HelperTools defaultsDB] synchronize];

    // xmpp connect checks NotificationServiceExtension via flock on locks/; without this,
    // MLProcessLock throws and connect never progresses past kStateReconnecting.
    [MLProcessLock initializeForProcess:@"MonalWire"];
    [MLProcessLock lock];

    NSString* dbPath = [[dataDir URLByAppendingPathComponent:@"sworim.sqlite"] path];
    if (![[NSFileManager defaultManager] fileExistsAtPath:dbPath]) {
        NSString* templatePath = [[NSBundle mainBundle] pathForResource:@"sworim" ofType:@"sqlite"];
        if (!templatePath.length) {
            NSString* interopRoot = [NSProcessInfo processInfo].environment[@"OMEMO_INTEROP_ROOT"];
            if (interopRoot.length) {
                templatePath = [interopRoot stringByAppendingPathComponent:@"vendor/monal/Monal/sworim.sqlite"];
            }
        }
        if (templatePath.length && [[NSFileManager defaultManager] fileExistsAtPath:templatePath]) {
            [[NSFileManager defaultManager] copyItemAtPath:templatePath toPath:dbPath error:&err];
            if (err) {
                @throw [NSException exceptionWithName:@"MonalWireBootstrap" reason:err.localizedDescription userInfo:nil];
            }
        }
    }
}

void MonalWireEnsurePlaintextHooks(void) {
    installWirePlaintextMlStream();
}
