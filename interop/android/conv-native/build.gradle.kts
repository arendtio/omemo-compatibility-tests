plugins {
    id("com.android.library") version "8.7.3"
}

val repoRoot = rootProject.file("../../").canonicalFile
val convRoot = repoRoot.resolve("vendor/conversations")
val convClasses =
    convRoot.resolve(
        "build/intermediates/javac/conversationsFreeDebug/compileConversationsFreeDebugJavaWithJavac/classes",
    )
val convBuildConfig =
    convRoot.resolve("build/generated/source/buildConfig/conversationsFree/debug")

tasks.register<Exec>("compileConversationsVendor") {
    group = "omemo"
    description = "Compile pinned Conversations vendor sources for native crypto tests"
    workingDir(convRoot)
    val gradlew = convRoot.resolve("gradlew")
    commandLine(gradlew.absolutePath, "compileConversationsFreeDebugJavaWithJavac", "-q")
    doFirst {
        val sdk = System.getenv("ANDROID_HOME") ?: System.getenv("ANDROID_SDK_ROOT")
        if (sdk.isNullOrBlank()) {
            throw GradleException("ANDROID_HOME required to compile vendor/conversations")
        }
        val localProps = convRoot.resolve("local.properties")
        if (!localProps.exists()) {
            localProps.writeText("sdk.dir=$sdk\n")
        }
    }
}

tasks.register<Jar>("packageConversationsVendorJar") {
    group = "omemo"
    description = "Package compiled Conversations vendor classes for native crypto tests"
    dependsOn("compileConversationsVendor")
    archiveBaseName.set("conversations-vendor")
    from(convClasses, convBuildConfig)
    duplicatesStrategy = DuplicatesStrategy.EXCLUDE
}

android {
    namespace = "org.omemo.interop.conv"
    compileSdk = 36

    defaultConfig {
        minSdk = 23
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }

    testOptions {
        unitTests.isIncludeAndroidResources = true
    }
}

tasks.named("preBuild") {
    dependsOn("packageConversationsVendorJar")
}

dependencies {
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.robolectric:robolectric:4.16.1")
    testImplementation("androidx.test:core:1.6.1")
    testImplementation("org.whispersystems:signal-protocol-java:2.6.2")
    testImplementation("com.google.guava:guava:33.6.0-android")
    testImplementation("androidx.appcompat:appcompat:1.7.1")
    testImplementation("androidx.preference:preference:1.2.1")
    testImplementation("com.google.code.gson:gson:2.11.0")
    testImplementation("com.squareup.okhttp3:okhttp:5.3.2")
    testImplementation("com.squareup.retrofit2:retrofit:3.0.0")
    testImplementation("com.squareup.retrofit2:converter-gson:3.0.0")
    testImplementation("com.google.android.material:material:1.14.0")
    testImplementation("androidx.concurrent:concurrent-futures:1.3.0")
    testImplementation("androidx.work:work-runtime:2.11.2")
    testImplementation("org.minidns:minidns-client:1.1.1")
    testImplementation("org.minidns:minidns-dnssec:1.1.1")
    testImplementation("org.jxmpp:jxmpp-jid:1.1.0")
    testImplementation("org.jxmpp:jxmpp-stringprep-libidn:1.1.0")
    testImplementation("org.bouncycastle:bcmail-jdk18on:1.84")
    testImplementation("org.conscrypt:conscrypt-android:2.5.3")
    testImplementation("org.immutables:value-annotations:2.12.2")
    testImplementation("com.github.open-keychain.open-keychain:openpgp-api:v5.7.1")
    testImplementation(
        files(
            tasks.named<Jar>("packageConversationsVendorJar").map { it.archiveFile.get().asFile },
        ),
    )
}

tasks.register("conversationsNativeCryptoTest") {
    group = "omemo"
    description = "Run Conversations vendor axolotl native crypto tests"
    dependsOn("testDebugUnitTest")
}

tasks.register<Test>("conversationsCryptoWire") {
    group = "omemo"
    description = "Headless wire scenario using Conversations vendor axolotl (Robolectric JVM)"
    val unitTest = tasks.named<Test>("testDebugUnitTest").get()
    testClassesDirs = unitTest.testClassesDirs
    classpath = unitTest.classpath
    dependsOn("packageConversationsVendorJar", "compileDebugUnitTestJavaWithJavac")
    filter {
        includeTestsMatching("eu.siacs.conversations.crypto.axolotl.ConversationsNativeWireMainTest")
    }
    testLogging {
        events("passed", "failed", "standardOut")
        showStandardStreams = true
    }
    systemProperty("wire.mode", findProperty("wireMode")?.toString() ?: "local_roundtrip")
}
