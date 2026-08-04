#import "WireBootstrap.h"
#import <objc/runtime.h>
#import <monalxmpp/HelperTools.h>

static NSURL* wireDataDir = nil;

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

    // Headless wire: skip device-id migration that reads keychain (Rust panic in simulator CLI).
    [[HelperTools defaultsDB] setBool:YES forKey:@"isSandboxAPNS"];
    [[HelperTools defaultsDB] setBool:NO forKey:@"udpLoggerEnabled"];
    [[HelperTools defaultsDB] synchronize];

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
