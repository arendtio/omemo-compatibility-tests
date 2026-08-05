#import "MonalWireLog.h"

static NSURL* wireLogFile = nil;

void MonalWireLogInstall(NSURL* dataDir) {
    if (!dataDir) {
        return;
    }
    wireLogFile = [dataDir URLByAppendingPathComponent:@"wire-debug.log"];
    [[NSFileManager defaultManager] createDirectoryAtURL:dataDir
                             withIntermediateDirectories:YES
                                              attributes:nil
                                                   error:nil];
    [@"" writeToURL:wireLogFile atomically:YES encoding:NSUTF8StringEncoding error:nil];
}

void MonalWireLog(const char* line) {
    if (!line) {
        return;
    }
    fprintf(stderr, "MonalWire: %s\n", line);
    fflush(stderr);
    if (!wireLogFile) {
        return;
    }
    NSString* entry = [NSString stringWithFormat:@"MonalWire: %s\n", line];
    NSFileHandle* handle = [NSFileHandle fileHandleForWritingAtPath:wireLogFile.path];
    if (!handle) {
        return;
    }
    @try {
        [handle seekToEndOfFile];
        [handle writeData:[entry dataUsingEncoding:NSUTF8StringEncoding]];
        [handle synchronizeFile];
    } @catch (NSException* e) {
        (void)e;
    } @finally {
        [handle closeFile];
    }
}
