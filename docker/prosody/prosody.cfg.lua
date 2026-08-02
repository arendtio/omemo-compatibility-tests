-- Prosody configuration for OMEMO legacy axolotl interop tests.
-- Open PEP/pubsub access so clients can fetch bundles without roster subscription.

component_paths = { "/usr/lib/prosody" }
plugin_paths = { "/usr/lib/prosody/modules" }

admins = { "admin@localhost" }

modules_enabled = {
    "roster";
    "saslauth";
    "tls";
    "dialback";
    "disco";
    "carbons";
    "pep";
    "private";
    "blocklist";
    "vcard";
    "version";
    "uptime";
    "time";
    "ping";
    "register";
    "admin_adhoc";
}

allow_registration = true
c2s_require_encryption = false
s2s_require_encryption = false

pep_auto_subscribe = true
pep_persistent_items = true

VirtualHost "localhost"
    authentication = "internal_plain"

Component "pubsub.localhost" "pubsub"
    modules_enabled = { "pubsub" }
    restrict_room_creation = false
    default_public_nodes = true
