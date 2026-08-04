#import "WireBootstrap.h"
#import <objc/runtime.h>
#import <SAMKeychain/SAMKeychain.h>
#import <monalxmpp/HelperTools.h>
#import <monalxmpp/MLProcessLock.h>

static NSURL* wireDataDir = nil;
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
