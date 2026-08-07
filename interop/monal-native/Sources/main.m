#import <Foundation/Foundation.h>
#import "MonalWireClient.h"
#import "WireBootstrap.h"

static void usage(void) {
    fprintf(stderr, "Usage: MonalWire --mode <publish|hold-send|send|wait> [--peer JID] [--send BODY] [--expect BODY] -- --jid JID --password PASS [--host HOST] [--port PORT] [--data-dir PATH]\n");
}

int main(int argc, char* argv[]) {
    @autoreleasepool {
        NSString* mode = nil;
        NSString* peer = nil;
        NSString* sendBody = nil;
        NSString* expectBody = nil;
        NSString* jid = nil;
        NSString* password = nil;
        NSString* host = @"127.0.0.1";
        int port = 5222;
        NSString* dataDirPath = @"omemo-wire-data";

        int split = -1;
        for (int i = 1; i < argc; i++) {
            if (strcmp(argv[i], "--") == 0) {
                split = i;
                break;
            }
        }

        int modeEnd = split >= 0 ? split : argc;
        for (int i = 1; i < modeEnd; i++) {
            if (strcmp(argv[i], "--mode") == 0 && i + 1 < modeEnd) {
                mode = [NSString stringWithUTF8String:argv[++i]];
            } else if (strcmp(argv[i], "--peer") == 0 && i + 1 < modeEnd) {
                peer = [NSString stringWithUTF8String:argv[++i]];
            } else if (strcmp(argv[i], "--send") == 0 && i + 1 < modeEnd) {
                sendBody = [NSString stringWithUTF8String:argv[++i]];
            } else if (strcmp(argv[i], "--expect") == 0 && i + 1 < modeEnd) {
                expectBody = [NSString stringWithUTF8String:argv[++i]];
            } else {
                fprintf(stderr, "Unknown arg: %s\n", argv[i]);
                return 1;
            }
        }

        if (split >= 0) {
            for (int i = split + 1; i < argc; i++) {
                if (strcmp(argv[i], "--jid") == 0 && i + 1 < argc) {
                    jid = [NSString stringWithUTF8String:argv[++i]];
                } else if (strcmp(argv[i], "--password") == 0 && i + 1 < argc) {
                    password = [NSString stringWithUTF8String:argv[++i]];
                } else if (strcmp(argv[i], "--host") == 0 && i + 1 < argc) {
                    host = [NSString stringWithUTF8String:argv[++i]];
                } else if (strcmp(argv[i], "--port") == 0 && i + 1 < argc) {
                    port = atoi(argv[++i]);
                } else if (strcmp(argv[i], "--data-dir") == 0 && i + 1 < argc) {
                    dataDirPath = [NSString stringWithUTF8String:argv[++i]];
                } else {
                    fprintf(stderr, "Unknown client arg: %s\n", argv[i]);
                    return 1;
                }
            }
        }

        if (!jid || !password) {
            usage();
            return 1;
        }

        NSURL* dataDir = [NSURL fileURLWithPath:dataDirPath isDirectory:YES];
        // Bootstrap before any DataLayer / MLXMPPManager use (swizzles container paths + process lock).
        MonalWireBootstrapInstall(dataDir);

        MonalWireClient* client = [[MonalWireClient alloc] initWithJid:jid
                                                              password:password
                                                                  host:host
                                                                  port:port
                                                               dataDir:dataDir];

        printf("IMPLEMENTATION=monal\n");
        fflush(stdout);
        printf("VENDOR_REV=%s\n", client.vendorRevision.UTF8String);
        fflush(stdout);
        printf("NAMESPACE=eu.siacs.conversations.axolotl\n");
        fflush(stdout);
        printf("RUNNER=monal_native_mlomemo\n");
        fflush(stdout);

        NSError* err = nil;
        if (![client connectWithTimeout:420 error:&err]) {
            fprintf(stderr, "ERROR: connect failed: %s\n", err.localizedDescription.UTF8String);
            fflush(stderr);
            return 1;
        }

        if (![client waitForOmemoReadyWithTimeout:120 error:&err]) {
            fprintf(stderr, "ERROR: omemo not ready: %s\n", err.localizedDescription.UTF8String);
            fflush(stderr);
            return 1;
        }

        if ([mode isEqualToString:@"publish"]) {
            [client disconnect];
            printf("OK\n");
            return 0;
        }

        if ([mode isEqualToString:@"hold-send"]) {
            if (!peer || !sendBody) {
                fprintf(stderr, "hold-send requires --peer and --send\n");
                return 1;
            }
            [client preparePeer:peer error:&err];
            NSString* readyPath = [dataDir.path stringByAppendingPathComponent:@"wire-ready"];
            [@"ok" writeToFile:readyPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
            printf("READY\n");
            fflush(stdout);
            if (![client waitForSendSignalWithTimeout:600]) {
                fprintf(stderr, "TIMEOUT waiting for wire-send-now signal\n");
                [client disconnect];
                return 1;
            }
            if (![client sendEncrypted:peer body:sendBody error:&err]) {
                fprintf(stderr, "ERROR: send failed: %s\n", err.localizedDescription.UTF8String);
                [client disconnect];
                return 1;
            }
            [client disconnect];
            printf("OK\n");
            return 0;
        }

        if ([mode isEqualToString:@"wait"]) {
            if (!peer) {
                fprintf(stderr, "wait requires --peer (sender JID)\n");
                return 1;
            }
            if (![client preparePeer:peer error:&err]) {
                fprintf(stderr, "ERROR: preparePeer failed: %s\n", err.localizedDescription.UTF8String);
                return 1;
            }
            if (![client waitForPeerOmemoReadyWithTimeout:240 error:&err]) {
                fprintf(stderr, "ERROR: peer OMEMO not ready: %s\n", err.localizedDescription.UTF8String);
                fflush(stderr);
                return 1;
            }
        }

        NSString* readyPath = [dataDir.path stringByAppendingPathComponent:@"wire-ready"];
        [@"ok" writeToFile:readyPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
        printf("READY\n");
        fflush(stdout);

        if ([mode isEqualToString:@"send"]) {
            if (!peer || !sendBody) {
                fprintf(stderr, "send requires --peer and --send\n");
                return 1;
            }
            if (![client sendEncrypted:peer body:sendBody error:&err]) {
                fprintf(stderr, "ERROR: send failed: %s\n", err.localizedDescription.UTF8String);
                [client disconnect];
                return 1;
            }
            [client disconnect];
            printf("OK\n");
            return 0;
        }

        if ([mode isEqualToString:@"wait"]) {
            if (!expectBody) {
                fprintf(stderr, "wait requires --expect\n");
                return 1;
            }
            NSTimeInterval awaitTimeout = 300;
            NSString* awaitEnv = [NSProcessInfo processInfo].environment[@"MONAL_WIRE_AWAIT_TIMEOUT"];
            if (awaitEnv.length) {
                awaitTimeout = [awaitEnv doubleValue];
            }
            BOOL ok = [client awaitBody:expectBody timeout:awaitTimeout];
            [client disconnect];
            if (ok) {
                printf("OK\n");
                return 0;
            }
            fprintf(stderr, "TIMEOUT expected=%s\n", expectBody.UTF8String);
            return 1;
        }

        fprintf(stderr, "Unknown mode: %s\n", mode.UTF8String);
        return 1;
    }
}
