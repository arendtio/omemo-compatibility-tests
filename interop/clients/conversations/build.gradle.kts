plugins {
    application
}

dependencies {
    implementation(project(":common"))
}

application {
    mainClass.set("org.omemo.interop.conversations.ConversationsWireClient")
}

tasks.register("verifyConversationsVendor") {
    group = "verification"
    doLast {
        val root = System.getenv("OMEMO_INTEROP_ROOT") ?: rootProject.projectDir.parentFile.parent
        val conv = file("$root/vendor/conversations")
        if (!conv.exists()) {
            throw GradleException("vendor/conversations missing — run scripts/download-implementations.py")
        }
        val axolotl = file("$conv/src/main/java/eu/siacs/conversations/crypto/axolotl/XmppAxolotlMessage.java")
        if (!axolotl.exists()) {
            throw GradleException("Conversations axolotl sources not found in vendor checkout")
        }
    }
}

tasks.named("compileJava") {
    dependsOn("verifyConversationsVendor")
}
