"""Shared constants for OMEMO interoperability tests."""

from typing import Final

import oldmemo
import twomemo

NS_TWOMEMO: Final = twomemo.twomemo.NAMESPACE
NS_OLDMEMO: Final = oldmemo.oldmemo.NAMESPACE

ALICE_BARE_JID: Final = "alice@omemo-interop.test"
BOB_BARE_JID: Final = "bob@omemo-interop.test"
CAROL_BARE_JID: Final = "carol@omemo-interop.test"

# ejabberd docker-compose defaults
XMPP_DOMAIN: Final = "localhost"
XMPP_HOST: Final = "127.0.0.1"
XMPP_PORT: Final = 5222
