#import "MonalWireClient.h"
#import "WireBootstrap.h"

#import <monalxmpp/DataLayer.h>
#import <monalxmpp/HelperTools.h>
#import <monalxmpp/MLXMPPManager.h>
#import <monalxmpp/MLContact.h>
#import <monalxmpp/MLMessage.h>
#import <monalxmpp/MLConstants.h>
#import <monalxmpp/xmpp.h>

@interface MonalWireClient ()
@property(nonatomic, copy) NSString* jid;
@property(nonatomic, copy) NSString* password;
@property(nonatomic, copy) NSString* host;
@property(nonatomic, assign) int port;
@property(nonatomic, strong) NSURL* dataDir;
@property(nonatomic, strong) NSNumber* accountID;
@property(nonatomic, copy) NSString* lastBody;
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
    NSString* root = [NSProcessInfo processInfo].environment[@"OMEMO_INTEROP_ROOT"];
    if (!root.length) {
        return @"unknown";
    }
    NSString* monal = [root stringByAppendingPathComponent:@"vendor/monal"];
    NSTask* task = [[NSTask alloc] init];
    task.launchPath = @"/usr/bin/git";
    task.arguments = @[@"rev-parse", @"HEAD"];
    task.currentDirectoryPath = monal;
    NSPipe* pipe = [NSPipe pipe];
    task.standardOutput = pipe;
    [task launch];
    [task waitUntilExit];
    NSData* data = [[pipe fileHandleForReading] readDataToEndOfFile];
    NSString* rev = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    rev = [rev stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    return rev.length ? rev : @"unknown";
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
}

- (BOOL)connectWithTimeout:(NSTimeInterval)timeout error:(NSError**)error {
    MonalWireBootstrapInstall(self.dataDir);
    [HelperTools initSystem];

    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleNewMessage:)
                                                 name:kMonalNewMessageNotice
                                               object:nil];

    MLXMPPManager* manager = [MLXMPPManager sharedInstance];
    NSString* portStr = [NSString stringWithFormat:@"%d", self.port];
    NSNumber* accountID = [manager login:self.jid
                                  password:self.password
                            hardcodedServer:self.host
                            hardcodedPort:portStr
                            forceDirectTLS:NO
                            allowPlainAuth:YES];
    if (!accountID) {
        if (error) {
            *error = [NSError errorWithDomain:@"MonalWire" code:1 userInfo:@{NSLocalizedDescriptionKey: @"login failed (account may already exist in data dir)"}];
        }
        return NO;
    }
    self.accountID = accountID;

    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    xmpp* acc = nil;
    while ([deadline timeIntervalSinceNow] > 0) {
        acc = [self account];
        if (acc && acc.accountState >= kStateInitStarted) {
            break;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    }
    acc = [self account];
    if (!acc || acc.accountState < kStateInitStarted) {
        if (error) {
            *error = [NSError errorWithDomain:@"MonalWire" code:2 userInfo:@{NSLocalizedDescriptionKey: @"timeout waiting for XMPP session"}];
        }
        return NO;
    }

  deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    while ([deadline timeIntervalSinceNow] > 0) {
        if (acc.accountState >= kStateCatchupDone) {
            return YES;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    }
    if (error) {
        *error = [NSError errorWithDomain:@"MonalWire" code:3 userInfo:@{NSLocalizedDescriptionKey: @"timeout waiting for catchup"}];
    }
    return NO;
}

- (BOOL)preparePeer:(NSString*)peerJid error:(NSError**)error {
    xmpp* acc = [self account];
    if (!acc) {
        if (error) {
            *error = [NSError errorWithDomain:@"MonalWire" code:4 userInfo:@{NSLocalizedDescriptionKey: @"not connected"}];
        }
        return NO;
    }
    MLContact* contact = [MLContact createContactFromJid:peerJid andAccountID:self.accountID];
    [[MLXMPPManager sharedInstance] addContact:contact];
    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:45];
    while ([deadline timeIntervalSinceNow] > 0) {
        if (acc.accountState >= kStateCatchupDone) {
            break;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.5]];
    }
    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:2.0]];
    return YES;
}

- (BOOL)sendEncrypted:(NSString*)peerJid body:(NSString*)body error:(NSError**)error {
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

- (BOOL)awaitBody:(NSString*)expected timeout:(NSTimeInterval)timeout {
    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:timeout];
    while ([deadline timeIntervalSinceNow] > 0) {
        if ([self.lastBody isEqualToString:expected]) {
            return YES;
        }
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.25]];
    }
    return [self.lastBody isEqualToString:expected];
}

- (void)disconnect {
    if (self.accountID) {
        [[MLXMPPManager sharedInstance] disconnectAccount:self.accountID withExplicitLogout:YES];
    }
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

@end
