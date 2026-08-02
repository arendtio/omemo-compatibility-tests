plugins {
    `java-library`
}

val smackVersion = "4.4.8"

dependencies {
    api("org.igniterealtime.smack:smack-tcp:$smackVersion")
    api("org.igniterealtime.smack:smack-extensions:$smackVersion")
    api("org.igniterealtime.smack:smack-im:$smackVersion")
    api("org.igniterealtime.smack:smack-omemo:$smackVersion")
    api("org.igniterealtime.smack:smack-omemo-signal:$smackVersion")
    runtimeOnly("org.igniterealtime.smack:smack-xmlparser-stax:$smackVersion")
    runtimeOnly("org.igniterealtime.smack:smack-java8:$smackVersion")
    implementation("org.bouncycastle:bcprov-jdk18on:1.78.1")
}
