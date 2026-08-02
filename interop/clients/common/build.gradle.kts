plugins {
    `java-library`
}

val smackVersion = "4.4.8"

dependencies {
    api("org.igniterealtime.smack:smack-tcp:$smackVersion")
    api("org.igniterealtime.smack:smack-extensions:$smackVersion")
    api("org.igniterealtime.smack:smack-omemo:$smackVersion")
    api("org.igniterealtime.smack:smack-omemo-signal:$smackVersion")
}
