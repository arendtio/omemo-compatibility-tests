#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@interface MonalWireClient : NSObject

@property(nonatomic, copy, readonly) NSString* jid;
@property(nonatomic, copy, readonly) NSString* password;
@property(nonatomic, copy, readonly) NSString* host;
@property(nonatomic, assign, readonly) int port;
@property(nonatomic, strong, readonly) NSURL* dataDir;

- (instancetype)initWithJid:(NSString*)jid
                     password:(NSString*)password
                         host:(NSString*)host
                         port:(int)port
                      dataDir:(NSURL*)dataDir;

- (NSString*)vendorRevision;
- (BOOL)connectWithTimeout:(NSTimeInterval)timeout error:(NSError**)error;
- (BOOL)waitForOmemoReadyWithTimeout:(NSTimeInterval)timeout error:(NSError**)error;
- (BOOL)preparePeer:(NSString*)peerJid error:(NSError**)error;
- (BOOL)waitForPeerOmemoReadyWithTimeout:(NSTimeInterval)timeout error:(NSError**)error;
- (BOOL)sendEncrypted:(NSString*)peerJid body:(NSString*)body error:(NSError**)error;
- (BOOL)awaitBody:(NSString*)expected timeout:(NSTimeInterval)timeout;
- (void)disconnect;

@end

NS_ASSUME_NONNULL_END
