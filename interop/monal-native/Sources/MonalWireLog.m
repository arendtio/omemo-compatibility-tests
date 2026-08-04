#import "MonalWireLog.h"

void MonalWireLog(const char* line) {
    if (!line) {
        return;
    }
    fprintf(stderr, "MonalWire: %s\n", line);
    fflush(stderr);
}
