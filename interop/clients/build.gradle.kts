allprojects {
    group = "org.omemo.interop"
    version = "0.2.0"

    repositories {
        mavenCentral()
    }
}

subprojects {
    apply(plugin = "java")

    tasks.withType<JavaCompile> {
        options.release.set(17)
    }
}
