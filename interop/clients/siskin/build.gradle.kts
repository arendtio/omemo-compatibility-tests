plugins {
    application
}

dependencies {
    implementation(project(":common"))
}

application {
    mainClass.set("org.omemo.interop.siskin.SiskinWireClient")
}

tasks.register("verifySiskinVendor") {
    group = "verification"
    doLast {
        val root = System.getenv("OMEMO_INTEROP_ROOT") ?: rootProject.projectDir.parentFile.parent
        val siskin = file("$root/vendor/siskin_im")
        if (!siskin.exists()) {
            throw GradleException("vendor/siskin_im missing — run scripts/download-implementations.py")
        }
        val projectFile = file("$siskin/SiskinIM.xcodeproj")
        if (!projectFile.exists()) {
            throw GradleException("SiskinIM.xcodeproj not found in vendor/siskin_im checkout")
        }
    }
}

tasks.named("compileJava") {
    dependsOn("verifySiskinVendor")
}
