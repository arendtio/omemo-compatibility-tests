plugins {
    application
}

dependencies {
    implementation(project(":common"))
}

application {
    mainClass.set("org.omemo.interop.monal.MonalWireClient")
}

tasks.register("verifyMonalVendor") {
    group = "verification"
    doLast {
        val root = System.getenv("OMEMO_INTEROP_ROOT") ?: rootProject.projectDir.parentFile.parent
        val monal = file("$root/vendor/monal")
        if (!monal.exists()) {
            throw GradleException("vendor/monal missing — run scripts/download-implementations.py")
        }
        val omemo = file("$monal/Monal/Classes/MLOMEMO.m")
        if (!omemo.exists()) {
            throw GradleException("MLOMEMO.m not found in vendor/monal checkout")
        }
    }
}

tasks.named("compileJava") {
    dependsOn("verifyMonalVendor")
}
